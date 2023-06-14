import json
import pathlib
import textwrap
import types
import typing
import zipfile
from copy import deepcopy
from importlib import resources

try:
    from importlib.resources.abc import Traversable
except ImportError:
    from importlib.abc import Traversable

import tomllib

import pydantic
import yaml

from . import utils
from .rules import base_models

Models: typing.TypeAlias = typing.Iterable[pydantic.BaseModel]
FeatureTypeMap: typing.TypeAlias = dict[str, typing.Type[base_models.BaseFeatureDef]]
PathLike: typing.TypeAlias = pathlib.Path | zipfile.Path | Traversable


def load_ruleset(
    path: str | PathLike, with_bad_defs: bool = True
) -> base_models.BaseRuleset:
    """Load the specified ruleset from disk by path.

    The ruleset path must be a directory containg file named
    "ruleset" with a json, toml, or yaml/yml extension.

    Args:
        path: Path to a directory that contains a ruleset file.
            Alternatively, a path to a zipfile that contains a ruleset
            file and additional ruleset data.
            If the given path is a string beginning with "$" and containing no slashes,
            it is interpreted as a resource path.
        with_bad_defs: If true (the default), will not raise an exception
            if a feature definition file has a bad definition. Instead,
            the returned ruleset will have its `bad_defs` property populated
            with BadDefinition models.
    """
    if isinstance(path, str):
        if path.startswith("$") and "/" not in path:
            # Assume this is a python package resource reference.
            path = resources.files(path[1:])
        elif path.endswith(".zip"):
            path = zipfile.Path(zipfile.ZipFile(path))
        else:
            path = pathlib.Path(path)
    # First, look for the ruleset.
    ruleset_path = _find_file(path, stem="ruleset", depth=1)
    if not ruleset_path:
        raise ValueError(f"No ruleset file found within {path}")
    ruleset = _parse_ruleset(ruleset_path)
    if not ruleset:
        raise ValueError(f"Path {path} does not contain a ruleset definition.")
    feature_defs = ruleset.feature_model_types()
    if not _verify_feature_model_class(feature_defs):
        raise ValueError(
            textwrap.dedent(
                f"""Feature definition must be a pydantic model or union
                of pydantic models, but got `{feature_defs}` instead."""
            )
        )
    feature_types = _feature_model_map(feature_defs)
    feature_dict: dict[str, base_models.BaseFeatureDef] = {}
    bad_defs: list[base_models.BadDefinition] = []
    for subpath in _iter_dirs(path):
        for model in _parse_directory(
            subpath, feature_types, with_bad_defs=with_bad_defs
        ):
            if isinstance(model, base_models.BadDefinition):
                bad_defs.append(model)
            elif duplicate := (
                ruleset.features.get(model.id)
                or feature_dict.get(model.id)
                or ruleset.attribute_map.get(model.id)
            ):
                bad_defs.append(
                    base_models.BadDefinition(
                        path=model.def_path,
                        data=model.dump(as_json=False),
                        raw_data=None,
                        exception_type="NonUniqueId",
                        exception_message=f"Non-unique ID {model.id}. Existing: {duplicate}",
                    )
                )
            else:
                feature_dict[model.id] = model
    ruleset = ruleset.copy(
        update={
            "features": ruleset.features | feature_dict,
            "bad_defs": bad_defs,
        }
    )
    broken_features: set[str] = set()
    for id, feature in ruleset.features.items():
        try:
            feature.post_validate(ruleset)
        except Exception as exc:
            if with_bad_defs:
                ruleset.bad_defs.append(
                    base_models.BadDefinition(
                        path=feature.def_path,
                        raw_data=None,
                        exception_type=type(exc).__name__,
                        exception_message=str(exc),
                    )
                )
                broken_features.add(id)
            else:
                raise
    for id in broken_features:
        del ruleset.features[id]
    try:
        # Ensure the ruleset's engine can be loaded.
        ruleset.engine
    except Exception as exc:
        if with_bad_defs:
            ruleset.bad_defs.append(
                base_models.BadDefinition(
                    path=feature.def_path,
                    raw_data=ruleset.engine_class,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
            )
        else:
            raise
    return ruleset


def deserialize_ruleset(json_data: str) -> base_models.BaseRuleset:
    ruleset_dict = json.loads(json_data)
    return _parse_ruleset_dict(ruleset_dict)


def _parse_ruleset(path: PathLike) -> base_models.BaseRuleset:
    """Parse a ruleset from its ruleset.(toml|json|ya?ml) file.

    The actual type of the ruleset depends on its contents, but
    will always be a subclass of BaseRuleset.
    """
    ruleset_dict = list(_parse_raw(path))[0]
    return _parse_ruleset_dict(ruleset_dict)


def _parse_ruleset_dict(ruleset_dict: dict):
    if "ruleset_model_def" not in ruleset_dict and "ruleset" not in ruleset_dict:
        raise ValueError(
            "Invalid ruleset definition, does not specifiy ruleset model definition"
        )
    ruleset_def: str
    if "ruleset_model_def" in ruleset_dict:
        ruleset_def = ruleset_dict["ruleset_model_def"]
    elif "ruleset" in ruleset_dict:
        ruleset_def = ruleset_dict["ruleset"] + ".Ruleset"
    ruleset_model = utils.import_name(ruleset_def)
    if not issubclass(ruleset_model, base_models.BaseRuleset):
        raise ValueError(f"{ruleset_def} does not implement BaseRuleset")
    return pydantic.parse_obj_as(ruleset_model, ruleset_dict)


def _parse_directory(
    path: PathLike,
    feature_types: FeatureTypeMap,
    with_bad_defs: bool = True,
    defaults=None,
) -> Models:
    defaults = defaults.copy() if defaults else {}
    # Load defaults. There's proably not more than one, but if so, okay I guess?
    for subpath in _iter_files(path, stem="__defaults__"):
        for raw_defaults in _parse_raw(subpath):
            defaults.update(raw_defaults)
    # Now parse files based on the defaults.
    for subpath in _iter_files(path):
        stem = _stem(subpath)
        if stem.startswith("_") or stem.startswith("."):
            # Ignore any other "special" files.
            # We may define some with meanings in the future.
            continue
        yield from _parse(
            subpath, feature_types, with_bad_defs=with_bad_defs, defaults=defaults
        )
    # Now parse subdirectories, passing our current defaults up.
    for subpath in _iter_dirs(path):
        yield from _parse_directory(
            subpath, feature_types, with_bad_defs=with_bad_defs, defaults=defaults
        )


def _iter_dirs(path: PathLike) -> typing.Iterable[PathLike]:
    for subpath in (p for p in path.iterdir()):
        if subpath.is_dir() and not _stem(subpath).startswith("."):
            yield subpath


def _iter_files(path: PathLike, stem=None, suffix=None) -> typing.Iterable[PathLike]:
    for subpath in (p for p in path.iterdir() if p.is_file()):
        if _stem(subpath).startswith("."):
            continue
        if stem and _stem(subpath) != stem:
            continue
        if suffix and not _suffix(subpath) != suffix:
            continue
        yield subpath


def _find_file(path: PathLike, stem=None, suffix=None, depth=0) -> PathLike | None:
    for subpath in _iter_files(path, stem=stem, suffix=suffix):
        return subpath

    if depth >= 1:
        for subpath in _iter_dirs(path):
            recur_path = _find_file(subpath, stem=stem, suffix=suffix, depth=depth - 1)
            if recur_path:
                return recur_path
    return None


def _stem(path: PathLike) -> str:
    if isinstance(path, zipfile.Path):
        return path.filename.stem  # type: ignore[attr-defined]
    return path.stem


def _suffix(path: PathLike) -> str:
    if isinstance(path, zipfile.Path):
        return path.filename.suffix  # type: ignore[attr-defined]
    return path.suffix


def _verify_feature_model_class(model: base_models.ModelDefinition) -> bool:
    if isinstance(model, types.UnionType):
        return all(_verify_feature_model_class(c) for c in model.__args__)
    elif issubclass(model, pydantic.BaseModel):
        return True
    return False


def _feature_model_map(model: base_models.ModelDefinition) -> FeatureTypeMap:
    if isinstance(model, types.UnionType):
        feature_map: FeatureTypeMap = dict()
        for m in (_feature_model_map(c) for c in model.__args__):
            feature_map.update(m)
        return feature_map
    elif issubclass(model, base_models.BaseFeatureDef):
        return {model.type_key(): model}
    else:
        raise TypeError(f"Expected feature type, got {model}")


def _parse(
    path: PathLike,
    feature_types: FeatureTypeMap,
    with_bad_defs: bool = True,
    defaults=None,
) -> Models:
    count = 0
    for raw_data in _parse_raw(path):
        if "id" not in raw_data:
            raw_data["id"] = _stem(path) + (f"[{count}]" if count else "")
        if raw_data["id"] == "__defaults__":
            # A YAML stream might have embedded defaults.
            # Add them to our existing defaults and skip the entry.
            # Note that these only apply to this file.
            del raw_data["id"]
            defaults = _dict_merge(defaults, raw_data)
            continue
        count += 1
        try:
            data = _dict_merge(defaults, raw_data)
            data["def_path"] = str(path)
            type_key = data.get("type")
            if not type_key:
                raise TypeError(
                    'Type key not specified for this entry (e.g., `type: "skill")`'
                )
            model = feature_types.get(type_key)
            if not model:
                raise TypeError(
                    f'No feature model corresponding to type key "{type_key}"'
                )
            obj = pydantic.parse_obj_as(model, data)
            yield obj
        except (TypeError, pydantic.ValidationError) as exc:
            if with_bad_defs:
                yield base_models.BadDefinition(
                    path=str(path),
                    data=data,
                    raw_data=raw_data,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
            else:
                raise


def _dict_merge(a: dict | None, b: dict | None) -> dict:
    """Similar to copying 'a' and updating it with 'b'.

    This will be applied recursively to any sub-dicts in common.

    TODO: Or at least, it will do that when I care enough. For
    now it just slaps them together and does a deepcopy.
    """
    return deepcopy((a or {}) | (b or {}))


def _parse_raw(path: PathLike) -> typing.Generator[dict, None, None]:
    match _suffix(path):
        case ".toml":
            parser = _parse_toml
        case ".json":
            parser = _parse_json
        case ".yaml" | ".yml":
            parser = _parse_yaml
        case _:
            return
    yield from parser(path)


def _parse_toml(path: PathLike) -> typing.Generator[dict, None, None]:
    with path.open("rb") as toml_file:
        yield tomllib.load(toml_file)


def _parse_json(path: PathLike) -> typing.Generator[dict, None, None]:
    with path.open("rb") as json_file:
        yield json.load(json_file)


def _parse_yaml(path: PathLike) -> typing.Generator[dict, None, None]:
    with path.open("rb") as yaml_file:
        yield from yaml.safe_load_all(yaml_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ruleset = load_ruleset(sys.argv[1])
        if ruleset.bad_defs:
            print("Bad defs:")
            print(ruleset.bad_defs)
        else:
            print(f"Ruleset {ruleset.name} parsed successfully.")
            print("Features:")
            current_type = None
            for id, fc in sorted(
                ruleset.features.items(), key=lambda item: item[1].type
            ):
                if current_type != fc.type:
                    current_type = fc.type
                    friendly_type = ruleset.type_names.get(current_type, current_type)
                    print(f"Type: {friendly_type}")
                print(f"- {id}: {fc.name}")

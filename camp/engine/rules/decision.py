from __future__ import annotations

import traceback as tb
from typing import Any
from typing import ClassVar

import pydantic
from pydantic import BaseModel
from pydantic import Field


class Decision(BaseModel):
    """
    Attributes:
        success: True if the mutation succeeds or query succeeds.
        needs_option: When returned from a query, will be True
            if the only thing missing from the feature is an option.
        reason: If success=False, explains why.
        amount: If the action is hypothetical, how much can it be done?
        need_currency: If the action requires more currency, how much of which ones?
        exception: If the action failed due to an exception, what did it say?
        traceback: If success=False, where was the decision generated? Under certain
            circumstances, might be populated even for success=True. Supply
            traceback=True to force capture the traceback.
        mutation_applied: If an operation mutated the model, this should be true.
            Following a mutation, if the character no longer validates, it will
            be rolled back to the most recent dump.

    Note that this object's truthiness is tied to its success attribute.
    """

    success: bool = False
    needs_option: bool = False
    reason: str | None = None
    amount: int | None = None
    need_currency: dict[str, int] | None = None
    mutation_applied: bool = False
    exception: str | None = Field(default=None, repr=False)
    traceback: str | None | bool = Field(default=None, repr=False)

    OK: ClassVar[Decision]

    @pydantic.root_validator(pre=True)
    def _capture_traceback(cls, values: dict[str, Any]) -> dict[str, Any]:
        success: bool | None = values.get("success")
        traceback: str | None | bool = values.get("traceback")
        if traceback is True or (traceback is None and not success):
            traceback = "".join(tb.format_stack(limit=5)[:-1])
        else:
            traceback = None
        values["traceback"] = traceback
        return values

    def __bool__(self) -> bool:
        return self.success

    class Config:
        allow_mutation = False


Decision.OK = Decision(success=True)
Decision.MUTATED = Decision(success=True, mutation_applied=True)

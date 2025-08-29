document.addEventListener('DOMContentLoaded', function () {
  // Feature modal spinner visibility
  document.body.addEventListener('htmx:configRequest', function () {
    const indicator = document.querySelector('#featureModalSpinner');
    if (indicator) {
      indicator.style.display = '';
    }
  });
  document.body.addEventListener('htmx:afterOnLoad', function () {
    const indicator = document.querySelector('#featureModalSpinner');
    if (indicator) {
      indicator.style.display = 'none';
    }
  });
});

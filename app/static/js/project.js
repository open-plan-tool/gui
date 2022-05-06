////////////////////////////////////////////// Animations on scroll
AOS.init({
  duration: 1000,
  disable: "mobile"
});

////////////////////////////////////////////// Enable tooltips everywhere
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
  return new bootstrap.Tooltip(tooltipTriggerEl)
})

////////////////////////////////////////////// My projects page
const projectWrap = document.querySelector('main');

// toggle HIDE/SHOW SCENARIOS text
projectWrap.addEventListener('click', function() {
  const collapsedScenariosBoxesExpanded = document.querySelectorAll('.btn.btn--action[aria-expanded="true"] .js-toggle-scenario-name');
  const collapsedScenariosBoxes = document.querySelectorAll('.btn.btn--action[aria-expanded="false"] .js-toggle-scenario-name');

  collapsedScenariosBoxesExpanded.forEach(function(item) {
    item.innerHTML = `{% blocktranslate %}` + "Hide scenarios" + `{% endblocktranslate %}`;
  });

  collapsedScenariosBoxes.forEach(function(item) {
    item.innerHTML = `{% blocktranslate %}` + "Show scenarios" + `{% endblocktranslate %}`;
  });
})

////////////////////////////////////////////// Show up system design error modal
// replace window.onload with other event
const systemDesignError = document.getElementById("js-system-design-error");

if (systemDesignError) {
  let designError = new bootstrap.Modal(systemDesignError, {});
  window.onload = function () {
    designError.show();
  };
}



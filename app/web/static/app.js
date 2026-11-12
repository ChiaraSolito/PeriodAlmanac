// Small progressive enhancements. Everything also works without JavaScript.
(function () {
  // Remove ok/err/undo from the address bar once shown, so a refresh doesn't repeat the message.
  function cleanUrl() {
    var url = new URL(window.location.href);
    var changed = false;
    ["ok", "err", "undo"].forEach(function (k) {
      if (url.searchParams.has(k)) { url.searchParams.delete(k); changed = true; }
    });
    if (changed) history.replaceState(history.state, "", url.pathname + url.search + url.hash);
  }

  // Toasts disappear by themselves (longer when they offer "Annulla").
  function armToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (t) {
      if (t.dataset.armed) return;
      t.dataset.armed = "1";
      var ms = t.querySelector("form") ? 10000 : 5000;
      setTimeout(function () { t.classList.add("hide"); }, ms);
    });
  }

  function onLoad() { cleanUrl(); armToasts(); }
  document.addEventListener("DOMContentLoaded", onLoad);
  document.addEventListener("htmx:afterSettle", onLoad);

  document.addEventListener("click", function (e) {
    var dismiss = e.target.closest("[data-dismiss]");
    if (dismiss) { dismiss.closest("[data-toast]").classList.add("hide"); return; }

    // Calendar: tap a past day to log a start on that date.
    var day = e.target.closest("[data-log-date]");
    if (day) {
      var dlg = document.getElementById("log-dialog");
      if (!dlg || !dlg.showModal) return;
      dlg.querySelector("[name=start_date]").value = day.dataset.logDate;
      dlg.querySelector("[data-label]").textContent = day.dataset.label;
      dlg.showModal();
      return;
    }
    if (e.target.matches("dialog")) e.target.close(); // click on the backdrop
  });
})();

// FilePortal front-end behaviour: password toggle, menus, upload UX.
(function () {
  "use strict";
  var ALLOWED = ["pdf", "png", "jpg", "jpeg"];
  var MAX_MB = 5;

  // Show / hide password
  document.querySelectorAll(".toggle-pw").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.parentElement.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  // Dropdown menus (user menu and per-row actions)
  function closeMenus(except) {
    document.querySelectorAll(".menu").forEach(function (m) {
      if (m !== except) {
        m.hidden = true;
        var t = m.parentElement.querySelector("button[aria-expanded]");
        if (t) t.setAttribute("aria-expanded", "false");
      }
    });
  }
  document.querySelectorAll(".user-btn, .icon-btn").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var menu = btn.parentElement.querySelector(".menu");
      closeMenus(menu);
      menu.hidden = !menu.hidden;
      btn.setAttribute("aria-expanded", String(!menu.hidden));
    });
  });
  document.addEventListener("click", function () { closeMenus(null); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenus(null); });

  // Confirm destructive actions
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.dataset.confirm)) e.preventDefault();
    });
  });

  // Upload cards: validate on the client for fast feedback (server re-validates)
  document.querySelectorAll(".dropzone").forEach(function (zone) {
    var input = zone.querySelector(".file-input");
    var submit = zone.querySelector("button[type=submit]");
    var label = zone.querySelector(".chosen");

    function check() {
      var file = input.files[0];
      submit.hidden = true;
      label.style.color = "";
      if (!file) { label.textContent = ""; return; }
      var ext = file.name.split(".").pop().toLowerCase();
      if (ALLOWED.indexOf(ext) === -1) {
        label.textContent = "Only PDF, PNG or JPEG files are allowed.";
        label.style.color = "#b42318"; input.value = ""; return;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        label.textContent = "File is too large (max " + MAX_MB + " MB).";
        label.style.color = "#b42318"; input.value = ""; return;
      }
      label.textContent = file.name;
      submit.hidden = false;
    }
    input.addEventListener("change", check);

    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("drag"); });
    });
    zone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; check(); }
    });
    zone.addEventListener("submit", function () { submit.disabled = true; submit.textContent = "Uploading…"; });
  });
})();

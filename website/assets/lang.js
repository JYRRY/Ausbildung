// Tiny language switcher: reads jyry_lang cookie and adds .lang-de / .lang-en
// class to <html>. Runs as early as possible (before paint) to avoid flicker.
(function () {
  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : null;
  }
  function setCookie(name, value) {
    document.cookie =
      name +
      "=" +
      encodeURIComponent(value) +
      "; path=/; max-age=" +
      60 * 60 * 24 * 365 +
      "; samesite=lax";
  }
  function apply(lang) {
    var html = document.documentElement;
    html.classList.remove("lang-de", "lang-en");
    html.classList.add("lang-" + lang);
    html.setAttribute("lang", lang);
  }
  var current = getCookie("jyry_lang");
  if (current !== "de" && current !== "en") current = "de";
  apply(current);

  // Wire up any .lang-toggle buttons present in the DOM.
  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll(".lang-toggle button[data-lang]");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var l = btn.getAttribute("data-lang");
        if (l !== "de" && l !== "en") return;
        setCookie("jyry_lang", l);
        apply(l);
      });
    });
  });
})();

(function () {
  function initCitationCopyButton() {
    var citeEl = document.querySelector("#quarto-citation .quarto-appendix-citeas");
    if (!citeEl) return;

    var label = citeEl.previousElementSibling;
    if (!label || !label.classList.contains("quarto-appendix-secondary-label")) return;

    var button = document.createElement("button");
    button.type = "button";
    button.className = "citation-copy-button";
    button.title = "Copy citation";
    button.setAttribute("aria-label", "Copy citation");
    button.innerHTML = '<i class="bi bi-clipboard"></i>';

    button.addEventListener("click", function () {
      navigator.clipboard.writeText(citeEl.innerText.trim()).then(function () {
        var icon = button.querySelector("i");
        icon.className = "bi bi-clipboard-check";
        button.classList.add("citation-copy-button-checked");
        button.title = "Copied!";
        setTimeout(function () {
          icon.className = "bi bi-clipboard";
          button.classList.remove("citation-copy-button-checked");
          button.title = "Copy citation";
        }, 1500);
      });
    });

    label.appendChild(button);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCitationCopyButton);
  } else {
    initCitationCopyButton();
  }
})();

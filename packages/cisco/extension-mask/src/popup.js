document.addEventListener("DOMContentLoaded", () => {
  const copyButton = document.getElementById("copyButton");

  copyButton.addEventListener("click", () => {
    console.debug("Copy button clicked.");
    browser.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      browser.tabs
        .sendMessage(tabs[0].id, { action: "getTextToCopy" })
        .then((textToCopy) => {
          // Copy the text to the clipboard
          return navigator.clipboard.writeText(textToCopy);
        })
        .then(() => {
          console.log("Text copied to clipboard");
        })
        .catch((err) => {
          console.error("Error copying text: ", err);
        });
    });
  });

  console.debug("Added popup listeners.");
});

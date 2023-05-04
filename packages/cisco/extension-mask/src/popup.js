// Action name to communicate across script files.
const COPY_TEXT_ACTION = "getTextToCopy";

const copyButton = document.getElementById("copyButton");

// Add listener to the copy button in the popup.
copyButton.addEventListener("click", () => {
  browser.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    // Send a message to the content script to get the text to copy.
    browser.tabs
      .sendMessage(tabs[0].id, { action: COPY_TEXT_ACTION })
      .then((textToCopy) => {
        return navigator.clipboard.writeText(textToCopy);
      })
      .then(() => {
        console.log("Text copied to clipboard.");
      })
      .catch((err) => {
        console.error("Error copying text: ", err);
      });
  });
});

console.debug("Popup listeners added.");

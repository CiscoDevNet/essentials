/**
 * Adds date and namespace to the given text, then logs to the console.
 * @param {string} text - Text to log
 */
function log(text, namespace) {
  const formattedNamespace = namespace ? ` ${namespace} ` : " ";
  console.log(`${new Date().toISOString()}${formattedNamespace}${text}`);
}

module.exports = { log };

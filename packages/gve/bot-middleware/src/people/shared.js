const { BASIC_PROPS } = require("./constants");

// https://jsperf.com/dictionary-contains-key
function hasAllProps(person, props = BASIC_PROPS) {
  try {
    return props.every((prop) => typeof person[prop] !== "undefined");
  } catch (error) {
    // ReferenceError: person is undefined
    return false;
  }
}

function joinArrays(objValue, srcValue) {
  if (Array.isArray(objValue)) {
    // Remove duplicate values.
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Set
    return [...new Set(objValue.concat(srcValue))];
  }
}

module.exports = {
  hasAllProps,
  joinArrays,
};

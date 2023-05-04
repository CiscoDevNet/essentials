import nlp from "compromise";

// Action name to communicate across script files.
const COPY_TEXT_ACTION = "getTextToCopy";

const NEXT_EVENT_LOOP = 0;

const PHONE_NUMBER_AREA_CODE = "555";
const PHONE_NUMBER_LENGTH = 7;

const peopleVars = new Map();
const emailVars = new Map();
const phoneVars = new Map();
const placeVars = new Map();
const orgVars = new Map();

/**
 * Wrap the variable name in `${}` to identify it as a variable placeholder.
 * @param {string} variableName
 * @returns formatted variable
 */
const formatVariable = (variableName) => {
  return `\${${variableName}}`;
};

/**
 * Generate a fake phone number using the given number as its base.
 * @param {number} number - plain number to incorporate into a fake phone number
 * @returns formatted phone number
 */
const formatPhoneNumber = (number) => {
  const paddedNumber = number.toString().padStart(PHONE_NUMBER_LENGTH, "0");
  const firstPart = paddedNumber.slice(0, 3);
  const secondPart = paddedNumber.slice(3);
  const formattedNumber = `${PHONE_NUMBER_AREA_CODE}_${firstPart}_${secondPart}`;
  return formatVariable(formattedNumber);
};

/**
 * Mask sensitive data in the given text.
 * @param {string} text - text with sensitive data
 * @returns text with placeholders instead of sensitive data
 */
const maskSensitiveData = (text) => {
  const doc = nlp(text);
  const people = doc.people().out("array");
  const emails = doc.emails().out("array");
  const phones = doc.phoneNumbers().out("array");
  const places = doc.places().out("array");
  const organizations = doc.organizations().out("array");

  people.forEach((person) => {
    if (!peopleVars.has(person)) {
      const peopleCount = peopleVars.size + 1;
      const formattedPerson = `PERSON_${peopleCount}`;
      peopleVars.set(person, formatVariable(formattedPerson));
    }

    text = text.replace(person, peopleVars.get(person));
  });

  emails.forEach((email) => {
    if (!emailVars.has(email)) {
      const emailNumber = emailVars.size + 1;
      const formattedEmail = `EMAIL_${emailNumber}@email.com`;
      emailVars.set(email, formatVariable(formattedEmail));
    }

    text = text.replace(email, emailVars.get(email));
  });

  phones.forEach((phone) => {
    if (!phoneVars.has(phone)) {
      const count = phoneVars.size + 1;
      const formattedNumber = formatPhoneNumber(count);
      phoneVars.set(phone, formattedNumber);
    }

    text = text.replace(phone, phoneVars.get(phone));
  });

  places.forEach((place) => {
    if (!placeVars.has(place)) {
      const placeCount = placeVars.size + 1;
      const formattedPlace = `PLACE_${placeCount}`;
      placeVars.set(place, formatVariable(formattedPlace));
    }

    text = text.replace(place, placeVars.get(place));
  });

  organizations.forEach((organization) => {
    if (!orgVars.has(organization)) {
      const orgCount = orgVars.size + 1;
      const formattedOrg = `ORGANIZATION_${orgCount}`;
      orgVars.set(organization, formatVariable(formattedOrg));
    }

    text = text.replace(organization, orgVars.get(organization));
  });

  return text;
};

/**
 * Determine if the element tag associated with this event is an input.
 * @param {Object} event
 * @returns true if the element tag associated with this event is an input
 */
const isInput = (event) => {
  const { tagName } = event.target;
  return tagName === "INPUT" || tagName === "TEXTAREA";
};

/**
 * Mask sensitive data in this input field.
 * @param {Object} event
 */
const maskInput = (event) => {
  const { target } = event;

  if (isInput(event)) {
    const inputText = target.value;

    // Data should be masked if the person is done typing -
    // if they typed a space or return.
    const shouldMask = inputText.endsWith(" ") || inputText.endsWith("\n");

    if (shouldMask) {
      target.value = maskSensitiveData(inputText);

      // Print replacement rules to the console.
      console.info(getBatchReplaceScript());
    }

    console.debug(`Processed ${target.tagName} from "${event.type}" event.`);
  }
};

/**
 * Generate a script in Batch Replace format to replace all masked data with
 * the original data.
 * @returns script in Batch Replace format
 * @see https://marketplace.visualstudio.com/items?itemName=angelomollame.batch-replacer
 */
const getBatchReplaceScript = () => {
  allVars = [peopleVars, emailVars, phoneVars, placeVars, orgVars];
  mappings = allVars.map((varsMapping) => formatMap(varsMapping));
  return mappings.join("\n");
};

/**
 * Format the given map as a Batch Replace script.
 * @param {Map} map - map of masked data to original data
 * @returns script in Batch Replace format
 * @see https://marketplace.visualstudio.com/items?itemName=angelomollame.batch-replacer
 * @example
 *
 * replace "Alice"
 * with "Bob"
 *
 * replace "Carol"
 * with "David"
 */
const formatMap = (map) => {
  const entries = Array.from(map.entries());
  const formattedEntries = entries.map(
    ([unmasked, masked]) => `replace "${masked}"\nwith "${unmasked}"\n`
  );
  return formattedEntries.join("\n");
};

// Add document listeners.

/**
 * Listen for paste events to trigger the input processing.
 */
document.addEventListener("paste", (event) => {
  if (isInput(event)) {
    setTimeout(() => {
      // Add whitespace to trigger the input processing.
      event.target.value += " ";

      // Manually trigger input event to format the data.
      const inputEvent = new Event("input", {
        bubbles: true,
        cancelable: true,
      });
      event.target.dispatchEvent(inputEvent);
    }, NEXT_EVENT_LOOP);
  }
});

/**
 * Listen for input events to trigger the input processing.
 */
document.addEventListener("input", maskInput);

/**
 * Listen for copy events from the background script `popup.js`.
 */
browser.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === COPY_TEXT_ACTION) {
    const textToCopy = getBatchReplaceScript();
    sendResponse(textToCopy);
  }
});

console.debug("Document listeners added.");

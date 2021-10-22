---
id: api
title: API
sidebar_position: 4
---
## Classes

<dl>
<dt><a href="#AnalyticsEvent">AnalyticsEvent</a></dt>
<dd><p>Creates a new AnalyticsEvent.</p>
</dd>
<dt><a href="#Command">Command</a></dt>
<dd><p>Creates a new base Command that handles a particular intent.
Specific commands</p>
</dd>
<dt><a href="#Analytics">Analytics</a></dt>
<dd><p>Middleware to track user events.</p>
<p>Properties sent to the analytics service are in snake_case,
based on <a href="https://segment.com/academy/collecting-data/naming-conventions-for-clean-data/">Segment naming conventions</a>.</p>
<p>Some properties are encrypted or excluded,
based on <a href="https://wiki.cisco.com/display/CTGPrivacy/Privacy+Rules+for+Spark+Message+Logs+and+Analytics"> Webex Teams recommendations</a>.</p>
<ul>
<li>Users identified by Webex Teams&#39; hashed ID</li>
<li>Org names/domain names are reported (not org ID)</li>
<li>Single event records do not include both sides of a communication</li>
</ul>
</dd>
<dt><a href="#Bridge">Bridge</a></dt>
<dd></dd>
<dt><a href="#Input">Input</a></dt>
<dd><p>Text input.</p>
</dd>
<dt><a href="#Auth">Auth</a></dt>
<dd></dd>
<dt><a href="#DeploymentConfigError">DeploymentConfigError</a></dt>
<dd></dd>
<dt><a href="#SalesforceError">SalesforceError</a></dt>
<dd></dd>
<dt><a href="#Salesforce">Salesforce</a></dt>
<dd></dd>
</dl>

## Constants

<dl>
<dt><a href="#UNKNOWN">UNKNOWN</a> : <code>String</code></dt>
<dd><p>Placeholder for unknown property value.</p>
</dd>
<dt><a href="#UNKNOWN_NUMBER">UNKNOWN_NUMBER</a> : <code>number</code></dt>
<dd><p>Placeholder for unknown number property value.</p>
</dd>
<dt><a href="#MESSAGE_SENT">MESSAGE_SENT</a> : <code>String</code></dt>
<dd><p>Event name when a message is sent by the user.</p>
</dd>
<dt><a href="#MESSAGE_RECEIVED">MESSAGE_RECEIVED</a> : <code>String</code></dt>
<dd><p>Event name when a bot sends a message to the user
and the user (presumably) receives it.</p>
</dd>
<dt><a href="#REGEX_NEVER_MATCH">REGEX_NEVER_MATCH</a> : <code>RegExp</code></dt>
<dd><p>A regular expression that never matches anything.</p>
</dd>
<dt><a href="#ATTACHMENT_EVENT">ATTACHMENT_EVENT</a> : <code>string</code></dt>
<dd><p>Name of the event fired when a user engages with
an attachment, e.g., an Adaptive Card.</p>
</dd>
<dt><a href="#INTENT_DETECTED_EVENT">INTENT_DETECTED_EVENT</a> : <code>string</code></dt>
<dd><p>Event name to emit when an intent is detected.</p>
</dd>
<dt><a href="#MESSAGE">MESSAGE</a> : <code>String</code></dt>
<dd><p>Message sent to a bot in a group space.</p>
</dd>
<dt><a href="#DIRECT_MESSAGE">DIRECT_MESSAGE</a> : <code>String</code></dt>
<dd><p>Message sent to a bot in a one-on-one space.</p>
</dd>
<dt><a href="#STANDARD_MESSAGE_TYPES">STANDARD_MESSAGE_TYPES</a> : <code>Object</code></dt>
<dd><p>Most common bot message types, e.g., &quot;message&quot;, &quot;direct_message&quot;.
Most bots will want to listen for both group and direct messages.</p>
</dd>
<dt><a href="#INTENT_MATCHING_TYPES">INTENT_MATCHING_TYPES</a> : <code>Object</code></dt>
<dd><p>Ways that a message intent can be detected -
with an official intent property, or through pattern-matching.</p>
</dd>
<dt><a href="#analyticsEvent">analyticsEvent</a></dt>
<dd><p>Analytics event.</p>
</dd>
<dt><a href="#searchOptions">searchOptions</a></dt>
<dd><p>Giphy search options</p>
</dd>
<dt><a href="#eventTemplate">eventTemplate</a></dt>
<dd><p>Custom event and properties for analytics.</p>
</dd>
<dt><a href="#TEXT_LIMIT">TEXT_LIMIT</a></dt>
<dd><p>Text limit to avoid DialogFlow error:
INVALID_ARGUMENT: Input text exceeds 256 characters.</p>
</dd>
<dt><a href="#BASIC_PROPS">BASIC_PROPS</a> : <code>Array.&lt;String&gt;</code></dt>
<dd><p>A person must have all of these properties defined to be considered &quot;data complete&quot;.</p>
</dd>
<dt><a href="#ARCHIVE">ARCHIVE</a></dt>
<dd><p>Backup directories and files as an archive.</p>
</dd>
<dt><a href="#DRY_RUN">DRY_RUN</a></dt>
<dd><p>Perform a dry run.</p>
</dd>
<dt><a href="#IGNORE_TIMESTAMPS">IGNORE_TIMESTAMPS</a></dt>
<dd><p>Ignore timestamps to force overwriting similar destination files.</p>
</dd>
<dt><a href="#RSYNC_OPTIONS">RSYNC_OPTIONS</a></dt>
<dd><p>Use these options for rysnc backup.</p>
</dd>
<dt><a href="#DEFAULT_CONFIG">DEFAULT_CONFIG</a> : <code><a href="#BridgeConfig">BridgeConfig</a></code></dt>
<dd><p>Default configuration</p>
</dd>
<dt><a href="#GOOGLE_CLOUD_PROJECT">GOOGLE_CLOUD_PROJECT</a></dt>
<dd></dd>
<dt><a href="#DEFAULT_RELEASES_DIRECTORY">DEFAULT_RELEASES_DIRECTORY</a> : <code>String</code></dt>
<dd><p>Release configuration directory.</p>
</dd>
<dt><a href="#DOCKER_COMPOSE_ORIG">DOCKER_COMPOSE_ORIG</a></dt>
<dd><p>&quot;docker-compose build&quot; command</p>
<p>&quot;docker compose&quot; and &quot;docker-compose&quot; are different.
Use docker-compose to enable builds with ARGS.</p>
</dd>
<dt><a href="#KUBERNETES_DEPLOYMENT">KUBERNETES_DEPLOYMENT</a></dt>
<dd><p>Deployment kinds</p>
</dd>
<dt><a href="#SOQL_WILDCARD">SOQL_WILDCARD</a></dt>
<dd><p>Encoded wildcard character for SOQL queries.</p>
</dd>
<dt><a href="#SOQL_WILDCARD">SOQL_WILDCARD</a></dt>
<dd><p>Encoded wildcard character for SOQL queries.</p>
</dd>
</dl>

## Functions

<dl>
<dt><a href="#getTime">getTime(date)</a></dt>
<dd><p>Returns the date&#39;s time in seconds.</p>
</dd>
<dt><a href="#main">main()</a></dt>
<dd><p>Runs the program, parsing any command line options first.</p>
</dd>
<dt><a href="#runBridge">runBridge(source, project, options, command)</a></dt>
<dd><p>Creates a new Bridge from the source, copying the source files to the given project
and excluding them from repo commits and package publishing.</p>
</dd>
<dt><a href="#getDomain">getDomain(url)</a> ⇒ <code>String</code></dt>
<dd><p>Returns the base domain from the given URL.</p>
</dd>
<dt><a href="#formatApiVersion">formatApiVersion(version)</a> ⇒</dt>
<dd><p>Formats the given version number, e.g., &quot;51.0&quot;.</p>
</dd>
<dt><a href="#getQueryPath">getQueryPath(version)</a> ⇒</dt>
<dd><p>Returns the query path, e.g., &quot;services/data/v51.0/query&quot;.</p>
</dd>
<dt><a href="#getSalesforceObjectsPath">getSalesforceObjectsPath(version)</a> ⇒</dt>
<dd><p>Returns the Salesforce objects path, e.g., &quot;services/data/v51.0/sobjects&quot;.</p>
</dd>
<dt><a href="#getServicesPath">getServicesPath(version)</a> ⇒</dt>
<dd><p>Returns the services path, e.g., &quot;services/data/v44.0&quot;</p>
</dd>
</dl>

## Typedefs

<dl>
<dt><a href="#CommandConfig">CommandConfig</a> : <code>Object</code></dt>
<dd><p>Command configuration</p>
</dd>
<dt><a href="#Message">Message</a> : <code>Object</code></dt>
<dd><p>A message</p>
</dd>
<dt><a href="#Message">Message</a> : <code>Object</code></dt>
<dd><p>A message</p>
</dd>
<dt><a href="#Command">Command</a> : <code>Object</code></dt>
<dd><p>A command</p>
</dd>
<dt><a href="#IntentConfig">IntentConfig</a> : <code>Object</code></dt>
<dd><p>Intent configuration</p>
</dd>
<dt><a href="#User">User</a> : <code>Object</code></dt>
<dd><p>User data.</p>
<p>Responses sent from the bot are not sent to a particular user,
but to a Webex Teams space. In order to track events
from the <a href="#User">User</a>&#39;s perspective, we need to internally track user data.</p>
</dd>
<dt><a href="#space">space</a> : <code>Object</code></dt>
<dd><p>Partial known space data.</p>
</dd>
<dt><a href="#Spaces">Spaces</a> : <code>Map</code></dt>
<dd><p>Known spaces.
Keys are of type <a href="Space.space_id">Space.space_id</a>.
Properties are of type <a href="Space">Space</a>.</p>
</dd>
<dt><a href="#UserProp">UserProp</a> : <code>Object</code></dt>
<dd><p>Map of user property names and formatting functions.</p>
</dd>
<dt><a href="#MinimalSpace">MinimalSpace</a> : <code>Object</code></dt>
<dd><p>The space with the message.
This space has only one property: an ID.</p>
</dd>
<dt><a href="#ShouldTrack">ShouldTrack</a> : <code>Object</code></dt>
<dd><p>If and why an event should be tracked or not tracked</p>
</dd>
<dt><a href="#MinimalUser">MinimalUser</a> : <code>Object</code></dt>
<dd><p>The user (person, bot) receiving a message.
This user has a minimal number of properties.</p>
</dd>
<dt><a href="#UserInfo">UserInfo</a> : <code>Object</code></dt>
<dd><p>User information for an analytics event</p>
</dd>
<dt><a href="#CredentialBody">CredentialBody</a> : <code>Object</code></dt>
<dd><p>A Google Auth CredentialBody</p>
</dd>
<dt><a href="#IntentConfig">IntentConfig</a> : <code>Object</code></dt>
<dd><p>Intent configuration</p>
</dd>
<dt><a href="#PhoneNumber">PhoneNumber</a> : <code>Object</code></dt>
<dd><p>Person&#39;s phone number.</p>
</dd>
<dt><a href="#Person">Person</a> : <code>Object</code></dt>
<dd><p>A typical bot user</p>
</dd>
<dt><a href="#People">People</a> : <code>Map</code></dt>
<dd><p>Known people.</p>
<p>Keys are of type <a href="Person.id">Person.id</a>.
Properties are of type <a href="#Person">Person</a>.</p>
</dd>
<dt><a href="#WebexPerson">WebexPerson</a> : <code>Object</code></dt>
<dd><p>A Webex user</p>
<p>Properties beginning with an underscore denote those
not normally in a Botkit Person object.</p>
</dd>
<dt><a href="#BridgeConfig">BridgeConfig</a> : <code>Object</code></dt>
<dd><p>Configuration options</p>
</dd>
<dt><a href="#Rollback">Rollback</a> : <code>Object</code></dt>
<dd><p>Rollback information</p>
</dd>
<dt><a href="#AdaptiveCard">AdaptiveCard</a> : <code>Object</code></dt>
<dd><p>Adaptive Card</p>
<p>Adaptive Card based on the <a href="https://adaptivecards.io/explorer/">Adaptive Card schema</a>.</p>
</dd>
<dt><a href="#ChoicesConfig">ChoicesConfig</a></dt>
<dd></dd>
<dt><a href="#Choice">Choice</a></dt>
<dd></dd>
<dt><a href="#CredentialBody">CredentialBody</a> : <code>Object</code></dt>
<dd><p>Google Auth CredentialBody</p>
</dd>
<dt><a href="#ReleaseConfig">ReleaseConfig</a> : <code>Object</code></dt>
<dd><p>Release configuration</p>
</dd>
<dt><a href="#SalesforceUser">SalesforceUser</a> : <code>Object</code></dt>
<dd><p>Salesforce user data.</p>
</dd>
</dl>

<a name="AnalyticsEvent"></a>

## AnalyticsEvent
Creates a new AnalyticsEvent.

**Kind**: global class  

* [AnalyticsEvent](#AnalyticsEvent)
    * [new AnalyticsEvent(name, properties)](#new_AnalyticsEvent_new)
    * [.updateProperty(name, value)](#AnalyticsEvent+updateProperty)

<a name="new_AnalyticsEvent_new"></a>

### new AnalyticsEvent(name, properties)

| Param | Type | Description |
| --- | --- | --- |
| name | <code>String</code> | Event name |
| properties | <code>Object</code> | Event properties |

<a name="AnalyticsEvent+updateProperty"></a>

### analyticsEvent.updateProperty(name, value)
Adds the given property and value to the event.
Converts the property name to `snake_case` to adhere to
[best practices](https://segment.com/docs/getting-started/04-full-install/#property-naming-best-practices).

**Kind**: instance method of [<code>AnalyticsEvent</code>](#AnalyticsEvent)  

| Param | Type | Description |
| --- | --- | --- |
| name | <code>String</code> | Property name |
| value | <code>String</code> | Property value |

<a name="Command"></a>

## Command
Creates a new base Command that handles a particular intent.
Specific commands

**Kind**: global class  

* [Command](#Command)
    * [new Command(config)](#new_Command_new)
    * _instance_
        * [.controller](#Command+controller)
        * [.updateController(controller)](#Command+updateController)
        * [.defaultHandleText()](#Command+defaultHandleText)
        * [.defaultHandleAttachment()](#Command+defaultHandleAttachment)
        * [.getIntent(message)](#Command+getIntent) ⇒ <code>boolean</code>
        * [._matchNamedIntent(intent)](#Command+_matchNamedIntent) ⇒ <code>Boolean</code>
    * _static_
        * [.getPhraseExpression(phrases)](#Command.getPhraseExpression) ⇒ <code>RegExp</code>
        * [.matchPhrase(message, phrase)](#Command.matchPhrase) ⇒ <code>boolean</code>

<a name="new_Command_new"></a>

### new Command(config)
Creates a new command.
Listens to direct and group messages by default.


| Param | Type | Description |
| --- | --- | --- |
| config | [<code>CommandConfig</code>](#CommandConfig) | optional configuration |

<a name="Command+controller"></a>

### command.controller
See "Getters and Setters":

**Kind**: instance property of [<code>Command</code>](#Command)  
**See**: https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/Inheritance  
<a name="Command+updateController"></a>

### command.updateController(controller)
Configures the controller to listen for the command phrases
and attachment actions, e.g., Adaptive Card actions.

**Kind**: instance method of [<code>Command</code>](#Command)  

| Param | Type |
| --- | --- |
| controller | <code>Botkit</code> | 

<a name="Command+defaultHandleText"></a>

### command.defaultHandleText()
Handles text commands by default.
Prints a debug statement.

**Kind**: instance method of [<code>Command</code>](#Command)  
<a name="Command+defaultHandleAttachment"></a>

### command.defaultHandleAttachment()
Handles attachments by default.
Prints a debug statement.

**Kind**: instance method of [<code>Command</code>](#Command)  
<a name="Command+getIntent"></a>

### command.getIntent(message) ⇒ <code>boolean</code>
Returns the detected intent of the message.
If there is no "official" intent attached, uses pattern-matching
to determine the intent from the command's list of phrases.

**Kind**: instance method of [<code>Command</code>](#Command)  
**Returns**: <code>boolean</code> - true if intent was detected, false if not  
**Emits**: <code>Intent#event:detected</code>  
**See**: https://botkit.ai/docs/v4/reference/core.html#hears  

| Param | Type |
| --- | --- |
| message | [<code>Message</code>](#Message) | 

<a name="Command+_matchNamedIntent"></a>

### command.\_matchNamedIntent(intent) ⇒ <code>Boolean</code>
Returns true if the intent name matches this intent, false otherwise.

**Kind**: instance method of [<code>Command</code>](#Command)  
**Returns**: <code>Boolean</code> - true if the intent name matches this intent  
**See**: https://stackoverflow.com/a/9436948/154065  

| Param | Type |
| --- | --- |
| intent | <code>String</code> \| <code>Object</code> | 

<a name="Command.getPhraseExpression"></a>

### Command.getPhraseExpression(phrases) ⇒ <code>RegExp</code>
Joins the given phrases into a regular expression.

**Kind**: static method of [<code>Command</code>](#Command)  
**Returns**: <code>RegExp</code> - joined phrases  

| Param | Type | Description |
| --- | --- | --- |
| phrases | <code>Array</code> | The phrases to join |

<a name="Command.matchPhrase"></a>

### Command.matchPhrase(message, phrase) ⇒ <code>boolean</code>
Returns true if the user's message text matches the list of command phrases.

**Kind**: static method of [<code>Command</code>](#Command)  
**Returns**: <code>boolean</code> - true if the user's message matches a known command  

| Param | Type | Description |
| --- | --- | --- |
| message | [<code>Message</code>](#Message) \| <code>string</code> | the user's message or message text |
| phrase | <code>RegExp</code> | the phrase to match |

<a name="Analytics"></a>

## Analytics
Middleware to track user events.

Properties sent to the analytics service are in snake_case,
based on [Segment naming conventions](https://segment.com/academy/collecting-data/naming-conventions-for-clean-data/).

Some properties are encrypted or excluded,
based on [ Webex Teams recommendations](https://wiki.cisco.com/display/CTGPrivacy/Privacy+Rules+for+Spark+Message+Logs+and+Analytics).

- Users identified by Webex Teams' hashed ID
- Org names/domain names are reported (not org ID)
- Single event records do not include both sides of a communication

**Kind**: global class  

* [Analytics](#Analytics)
    * [new Analytics(apiKey, config)](#new_Analytics_new)
    * _instance_
        * [.userProps](#Analytics+userProps)
        * [.trackUserMessage(bot, message, next)](#Analytics+trackUserMessage)
        * [.trackBotMessage(bot, message, next)](#Analytics+trackBotMessage)
        * [._getAdditionalUserProps(user)](#Analytics+_getAdditionalUserProps) ⇒ <code>Object</code>
        * [._getSpaceInfo(minimalSpace)](#Analytics+_getSpaceInfo) ⇒ <code>Object</code>
        * [._getUserInfo(user)](#Analytics+_getUserInfo) ⇒ [<code>UserInfo</code>](#UserInfo)
        * [._getStandardInfo(timestamp)](#Analytics+_getStandardInfo) ⇒ <code>Object</code>
    * _static_
        * [.PROPERTY_VALUES](#Analytics.PROPERTY_VALUES)

<a name="new_Analytics_new"></a>

### new Analytics(apiKey, config)

| Param | Type | Description |
| --- | --- | --- |
| apiKey | <code>String</code> | the analytics service API key |
| config | <code>Object</code> | configuration details |
| config.appEnvironment | <code>Object</code> | application environment, e.g., development, staging |
| config.appVersion | <code>Object</code> | application version |
| config.url | <code>String</code> | the analytics service URL |
| config.userProps | <code>Array.&lt;(String\|UserProps)&gt;</code> | the additional user properties to track |

<a name="Analytics+userProps"></a>

### analytics.userProps
Sets additional user properties to pick from each incoming message.

**Kind**: instance property of [<code>Analytics</code>](#Analytics)  

| Param | Type | Description |
| --- | --- | --- |
| props | <code>Map</code> \| <code>Array.&lt;Array.&lt;String&gt;&gt;</code> | user property names and friendly names |

<a name="Analytics+trackUserMessage"></a>

### analytics.trackUserMessage(bot, message, next)
Tracks messages from the user to the bot.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Note**: Use with the middleware `receive` function.  

| Param | Type |
| --- | --- |
| bot | <code>\*</code> | 
| message | <code>\*</code> | 
| next | <code>\*</code> | 

**Example**  
```js
const analyticsMiddleware = new Analytics();
 controller.middleware.receive.use(analyticsMiddleware.trackUserMessage);
```
<a name="Analytics+trackBotMessage"></a>

### analytics.trackBotMessage(bot, message, next)
Tracks messages from the bot to the user.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Note**: Use with the middleware `send` function.  

| Param | Type |
| --- | --- |
| bot | <code>\*</code> | 
| message | <code>\*</code> | 
| next | <code>\*</code> | 

**Example**  
```js
const analyticsMiddleware = new Analytics();
 controller.middleware.send.use(analyticsMiddleware.trackBotMessage);
```
<a name="Analytics+_getAdditionalUserProps"></a>

### analytics.\_getAdditionalUserProps(user) ⇒ <code>Object</code>
Get the additional, desired user properties.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Returns**: <code>Object</code> - additional user properties  

| Param | Type | Description |
| --- | --- | --- |
| user | <code>Object</code> | additional user info attached to the message |

<a name="Analytics+_getSpaceInfo"></a>

### analytics.\_getSpaceInfo(minimalSpace) ⇒ <code>Object</code>
Gets more space information.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Returns**: <code>Object</code> - space with more details  

| Param | Type | Description |
| --- | --- | --- |
| minimalSpace | [<code>MinimalSpace</code>](#MinimalSpace) | space with the message |

<a name="Analytics+_getUserInfo"></a>

### analytics.\_getUserInfo(user) ⇒ [<code>UserInfo</code>](#UserInfo)
Gets the user properties for the analytics event.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Returns**: [<code>UserInfo</code>](#UserInfo) - user information for an analytics event  

| Param | Type |
| --- | --- |
| user | [<code>MinimalUser</code>](#MinimalUser) | 

<a name="Analytics+_getStandardInfo"></a>

### analytics.\_getStandardInfo(timestamp) ⇒ <code>Object</code>
Gets information standard to all analytics events.

**Kind**: instance method of [<code>Analytics</code>](#Analytics)  
**Returns**: <code>Object</code> - app version and time  

| Param | Type | Description |
| --- | --- | --- |
| timestamp | <code>number</code> | time in seconds |

<a name="Analytics.PROPERTY_VALUES"></a>

### Analytics.PROPERTY\_VALUES
Attach "static" property to the class.

**Kind**: static property of [<code>Analytics</code>](#Analytics)  
**See**: https://stackoverflow.com/a/48012789/154065  
<a name="Bridge"></a>

## Bridge
**Kind**: global class  

* [Bridge](#Bridge)
    * [new Bridge(source, project, config)](#new_Bridge_new)
    * _instance_
        * [.source](#Bridge+source)
        * [.project](#Bridge+project)
        * [.copy()](#Bridge+copy) ⇒ <code>String</code>
        * [.gitIgnore()](#Bridge+gitIgnore)
        * [._rollbackFile(original, backup)](#Bridge+_rollbackFile) ⇒ [<code>Rollback</code>](#Rollback)
        * [.publishIgnore()](#Bridge+publishIgnore)
    * _static_
        * [.isMonoRepo(project)](#Bridge.isMonoRepo) ⇒ <code>boolean</code>
        * [.copy()](#Bridge.copy) ⇒ <code>String</code>
        * [.isDirectory(dir)](#Bridge.isDirectory) ⇒ <code>boolean</code>

<a name="new_Bridge_new"></a>

### new Bridge(source, project, config)
Creates a new Bridge from the source to the destination project.


| Param | Type | Description |
| --- | --- | --- |
| source | <code>String</code> | the source directory |
| project | <code>String</code> | the destination project directory |
| config | [<code>BridgeConfig</code>](#BridgeConfig) | configuration options |

<a name="Bridge+source"></a>

### bridge.source
Sets the source directory.

**Kind**: instance property of [<code>Bridge</code>](#Bridge)  
**Throws**:

- <code>DirectoryError</code> 

<a name="Bridge+project"></a>

### bridge.project
Sets the project directory.

**Kind**: instance property of [<code>Bridge</code>](#Bridge)  
**Throws**:

- <code>DirectoryError</code> 
- <code>ProjectError</code> 

<a name="Bridge+copy"></a>

### bridge.copy() ⇒ <code>String</code>
Copies files from the source directory to the project destination directory.

**Kind**: instance method of [<code>Bridge</code>](#Bridge)  
**Returns**: <code>String</code> - the destination path where files were copied  
**Throws**:

- <code>SourceIsDestError</code> 

<a name="Bridge+gitIgnore"></a>

### bridge.gitIgnore()
Adds destination and backup file paths to .gitignore
so the files are not committed to the project repo.

**Kind**: instance method of [<code>Bridge</code>](#Bridge)  
<a name="Bridge+_rollbackFile"></a>

### bridge.\_rollbackFile(original, backup) ⇒ [<code>Rollback</code>](#Rollback)
Rolls back the file to the original copy.

**Kind**: instance method of [<code>Bridge</code>](#Bridge)  
**Returns**: [<code>Rollback</code>](#Rollback) - rollback information  
**Throws**:

- <code>RollbackError</code> 


| Param | Type | Description |
| --- | --- | --- |
| original | <code>\*</code> | the original file path |
| backup | <code>\*</code> | the backup file path |

<a name="Bridge+publishIgnore"></a>

### bridge.publishIgnore()
Adds destination file paths to the monorepo config.
These files will be ignored when publishing packages.

**Kind**: instance method of [<code>Bridge</code>](#Bridge)  
<a name="Bridge.isMonoRepo"></a>

### Bridge.isMonoRepo(project) ⇒ <code>boolean</code>
Returns true if the project is a valid monorepo, false otherwise.

**Kind**: static method of [<code>Bridge</code>](#Bridge)  
**Returns**: <code>boolean</code> - true if the project is a valid monorepo, false otherwise  

| Param | Type | Description |
| --- | --- | --- |
| project | <code>String</code> | the project directory |

<a name="Bridge.copy"></a>

### Bridge.copy() ⇒ <code>String</code>
Copies files from the source to the destination.

**Kind**: static method of [<code>Bridge</code>](#Bridge)  
**Returns**: <code>String</code> - the destination path where files were copied  
<a name="Bridge.isDirectory"></a>

### Bridge.isDirectory(dir) ⇒ <code>boolean</code>
Returns true if the given path is a directory, false otherwise.

**Kind**: static method of [<code>Bridge</code>](#Bridge)  
**Returns**: <code>boolean</code> - true if the given path is a directory, false otherwise  
**See**: https://stackoverflow.com/a/32749571/154065  

| Param | Type | Description |
| --- | --- | --- |
| dir | <code>String</code> | the directory path |

<a name="Input"></a>

## Input
Text input.

**Kind**: global class  
**See**: https://shoelace.style/components/form  
<a name="Auth"></a>

## Auth
**Kind**: global class  
**See**: https://www.npmjs.com/package/google-auth-library  

* [Auth](#Auth)
    * [.getCredentials(credentials)](#Auth.getCredentials) ⇒ [<code>CredentialBody</code>](#CredentialBody)
    * [.parseCredentials(credentials)](#Auth.parseCredentials) ⇒ [<code>CredentialBody</code>](#CredentialBody)

<a name="Auth.getCredentials"></a>

### Auth.getCredentials(credentials) ⇒ [<code>CredentialBody</code>](#CredentialBody)
Gets the authorization credentials.

**Kind**: static method of [<code>Auth</code>](#Auth)  
**Returns**: [<code>CredentialBody</code>](#CredentialBody) - credentials  

| Param | Type | Description |
| --- | --- | --- |
| credentials | <code>String</code> | file path or JSON string containing credentials |

<a name="Auth.parseCredentials"></a>

### Auth.parseCredentials(credentials) ⇒ [<code>CredentialBody</code>](#CredentialBody)
Parses the given credentials.

**Kind**: static method of [<code>Auth</code>](#Auth)  
**Returns**: [<code>CredentialBody</code>](#CredentialBody) - credentials needed to authorize  

| Param | Type | Description |
| --- | --- | --- |
| credentials | <code>String</code> | file path or JSON string containing credentials |

<a name="DeploymentConfigError"></a>

## DeploymentConfigError
**Kind**: global class  
<a name="new_DeploymentConfigError_new"></a>

### new DeploymentError(message)

| Param | Type | Description |
| --- | --- | --- |
| message | <code>String</code> | error message |

<a name="SalesforceError"></a>

## SalesforceError
**Kind**: global class  
<a name="new_SalesforceError_new"></a>

### new SalesforceError(message)

| Param | Type | Description |
| --- | --- | --- |
| message | <code>String</code> | error message |

<a name="Salesforce"></a>

## Salesforce
**Kind**: global class  
<a name="new_Salesforce_new"></a>

### new Salesforce(url, adapter)
Create instance of Salesforce controller


| Param | Type | Description |
| --- | --- | --- |
| url | <code>String</code> | Salesforce host address |
| adapter | <code>Object</code> | Salesforce adapter |

<a name="UNKNOWN"></a>

## UNKNOWN : <code>String</code>
Placeholder for unknown property value.

**Kind**: global constant  
<a name="UNKNOWN_NUMBER"></a>

## UNKNOWN\_NUMBER : <code>number</code>
Placeholder for unknown number property value.

**Kind**: global constant  
<a name="MESSAGE_SENT"></a>

## MESSAGE\_SENT : <code>String</code>
Event name when a message is sent by the user.

**Kind**: global constant  
<a name="MESSAGE_RECEIVED"></a>

## MESSAGE\_RECEIVED : <code>String</code>
Event name when a bot sends a message to the user
and the user (presumably) receives it.

**Kind**: global constant  
<a name="REGEX_NEVER_MATCH"></a>

## REGEX\_NEVER\_MATCH : <code>RegExp</code>
A regular expression that never matches anything.

**Kind**: global constant  
**See**: https://2ality.com/2012/09/empty-regexp.html  
<a name="ATTACHMENT_EVENT"></a>

## ATTACHMENT\_EVENT : <code>string</code>
Name of the event fired when a user engages with
an attachment, e.g., an Adaptive Card.

**Kind**: global constant  
<a name="INTENT_DETECTED_EVENT"></a>

## INTENT\_DETECTED\_EVENT : <code>string</code>
Event name to emit when an intent is detected.

**Kind**: global constant  
<a name="MESSAGE"></a>

## MESSAGE : <code>String</code>
Message sent to a bot in a group space.

**Kind**: global constant  
<a name="DIRECT_MESSAGE"></a>

## DIRECT\_MESSAGE : <code>String</code>
Message sent to a bot in a one-on-one space.

**Kind**: global constant  
<a name="STANDARD_MESSAGE_TYPES"></a>

## STANDARD\_MESSAGE\_TYPES : <code>Object</code>
Most common bot message types, e.g., "message", "direct_message".
Most bots will want to listen for both group and direct messages.

**Kind**: global constant  
<a name="INTENT_MATCHING_TYPES"></a>

## INTENT\_MATCHING\_TYPES : <code>Object</code>
Ways that a message intent can be detected -
with an official intent property, or through pattern-matching.

**Kind**: global constant  
<a name="analyticsEvent"></a>

## analyticsEvent
Analytics event.

**Kind**: global constant  
<a name="searchOptions"></a>

## searchOptions
Giphy search options

**Kind**: global constant  
**See**: https://developers.giphy.com/docs/api/endpoint/  
<a name="eventTemplate"></a>

## eventTemplate
Custom event and properties for analytics.

**Kind**: global constant  
<a name="TEXT_LIMIT"></a>

## TEXT\_LIMIT
Text limit to avoid DialogFlow error:
INVALID_ARGUMENT: Input text exceeds 256 characters.

**Kind**: global constant  
<a name="BASIC_PROPS"></a>

## BASIC\_PROPS : <code>Array.&lt;String&gt;</code>
A person must have all of these properties defined to be considered "data complete".

**Kind**: global constant  
<a name="ARCHIVE"></a>

## ARCHIVE
Backup directories and files as an archive.

**Kind**: global constant  
**See**: https://serverfault.com/a/141778/106402  
<a name="DRY_RUN"></a>

## DRY\_RUN
Perform a dry run.

**Kind**: global constant  
<a name="IGNORE_TIMESTAMPS"></a>

## IGNORE\_TIMESTAMPS
Ignore timestamps to force overwriting similar destination files.

**Kind**: global constant  
<a name="RSYNC_OPTIONS"></a>

## RSYNC\_OPTIONS
Use these options for rysnc backup.

**Kind**: global constant  
<a name="DEFAULT_CONFIG"></a>

## DEFAULT\_CONFIG : [<code>BridgeConfig</code>](#BridgeConfig)
Default configuration

**Kind**: global constant  
<a name="GOOGLE_CLOUD_PROJECT"></a>

## GOOGLE\_CLOUD\_PROJECT
**Kind**: global constant  
**See**: https://github.com/googleapis/google-auth-library-nodejs/blob/1ca3b733427d951ed624e1129fca510d84d5d0fe/src/auth/googleauth.ts#L646  
<a name="DEFAULT_RELEASES_DIRECTORY"></a>

## DEFAULT\_RELEASES\_DIRECTORY : <code>String</code>
Release configuration directory.

**Kind**: global constant  
<a name="DOCKER_COMPOSE_ORIG"></a>

## DOCKER\_COMPOSE\_ORIG
"docker-compose build" command

"docker compose" and "docker-compose" are different.
Use docker-compose to enable builds with ARGS.

**Kind**: global constant  
**See**: https://stackoverflow.com/a/67853849/154065  
<a name="KUBERNETES_DEPLOYMENT"></a>

## KUBERNETES\_DEPLOYMENT
Deployment kinds

**Kind**: global constant  
<a name="SOQL_WILDCARD"></a>

## SOQL\_WILDCARD
Encoded wildcard character for SOQL queries.

**Kind**: global constant  
<a name="SOQL_WILDCARD"></a>

## SOQL\_WILDCARD
Encoded wildcard character for SOQL queries.

**Kind**: global constant  
<a name="getTime"></a>

## getTime(date)
Returns the date's time in seconds.

**Kind**: global function  

| Param | Type | Description |
| --- | --- | --- |
| date | <code>Date</code> | the date to convert |

<a name="main"></a>

## main()
Runs the program, parsing any command line options first.

**Kind**: global function  
<a name="runBridge"></a>

## runBridge(source, project, options, command)
Creates a new Bridge from the source, copying the source files to the given project
and excluding them from repo commits and package publishing.

**Kind**: global function  
**See**: https://github.com/tj/commander.js#action-handler  

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| source | <code>String</code> |  | the source directory |
| project | <code>String</code> | <code>.</code> | the destination project directory |
| options | <code>Object</code> |  | the program options from the command line |
| command | <code>Object</code> |  | the program command |

<a name="getDomain"></a>

## getDomain(url) ⇒ <code>String</code>
Returns the base domain from the given URL.

**Kind**: global function  
**Returns**: <code>String</code> - domain of the URL  

| Param | Type |
| --- | --- |
| url | <code>URL</code> \| <code>String</code> | 

<a name="formatApiVersion"></a>

## formatApiVersion(version) ⇒
Formats the given version number, e.g., "51.0".

**Kind**: global function  
**Returns**: formatted API version number  

| Param | Type | Description |
| --- | --- | --- |
| version | <code>String</code> \| <code>number</code> | API version number |

<a name="getQueryPath"></a>

## getQueryPath(version) ⇒
Returns the query path, e.g., "services/data/v51.0/query".

**Kind**: global function  
**Returns**: the Salesforce query path  

| Param | Type | Description |
| --- | --- | --- |
| version | <code>String</code> | formatted API version number |

<a name="getSalesforceObjectsPath"></a>

## getSalesforceObjectsPath(version) ⇒
Returns the Salesforce objects path, e.g., "services/data/v51.0/sobjects".

**Kind**: global function  
**Returns**: the Salesforce objects path  

| Param | Type | Description |
| --- | --- | --- |
| version | <code>String</code> | formatted API version number |

<a name="getServicesPath"></a>

## getServicesPath(version) ⇒
Returns the services path, e.g., "services/data/v44.0"

**Kind**: global function  
**Returns**: the services path  

| Param | Type | Description |
| --- | --- | --- |
| version | <code>String</code> | formatted API version number |

<a name="CommandConfig"></a>

## CommandConfig : <code>Object</code>
Command configuration

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| intent | <code>String</code> | name of the intent |
| messageTypes | <code>Array.&lt;string&gt;</code> | Types of messages to listen for, e.g., a direct (1-on-1) message |
| phrases | <code>Array.&lt;string&gt;</code> | Phrases to listen for |
| handleText | <code>function</code> | Handles message text |
| handleAttachment | <code>function</code> | Handles message attachment actions, e.g., Adaptive Card clicks |
| friendlyName | <code>string</code> | Friendly name of the command |

<a name="Message"></a>

## Message : <code>Object</code>
A message

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| _intent | <code>Object</code> | The detected user intent |
| text | <code>string</code> | The message text |

<a name="Message"></a>

## Message : <code>Object</code>
A message

**Kind**: global typedef  
<a name="Command"></a>

## Command : <code>Object</code>
A command

**Kind**: global typedef  
**Properties**

| Name | Type |
| --- | --- |
| friendlyName | <code>String</code> | 


* [Command](#Command) : <code>Object</code>
    * [new Command(config)](#new_Command_new)
    * _instance_
        * [.controller](#Command+controller)
        * [.updateController(controller)](#Command+updateController)
        * [.defaultHandleText()](#Command+defaultHandleText)
        * [.defaultHandleAttachment()](#Command+defaultHandleAttachment)
        * [.getIntent(message)](#Command+getIntent) ⇒ <code>boolean</code>
        * [._matchNamedIntent(intent)](#Command+_matchNamedIntent) ⇒ <code>Boolean</code>
    * _static_
        * [.getPhraseExpression(phrases)](#Command.getPhraseExpression) ⇒ <code>RegExp</code>
        * [.matchPhrase(message, phrase)](#Command.matchPhrase) ⇒ <code>boolean</code>

<a name="new_Command_new"></a>

### new Command(config)
Creates a new command.
Listens to direct and group messages by default.


| Param | Type | Description |
| --- | --- | --- |
| config | [<code>CommandConfig</code>](#CommandConfig) | optional configuration |

<a name="Command+controller"></a>

### command.controller
See "Getters and Setters":

**Kind**: instance property of [<code>Command</code>](#Command)  
**See**: https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/Inheritance  
<a name="Command+updateController"></a>

### command.updateController(controller)
Configures the controller to listen for the command phrases
and attachment actions, e.g., Adaptive Card actions.

**Kind**: instance method of [<code>Command</code>](#Command)  

| Param | Type |
| --- | --- |
| controller | <code>Botkit</code> | 

<a name="Command+defaultHandleText"></a>

### command.defaultHandleText()
Handles text commands by default.
Prints a debug statement.

**Kind**: instance method of [<code>Command</code>](#Command)  
<a name="Command+defaultHandleAttachment"></a>

### command.defaultHandleAttachment()
Handles attachments by default.
Prints a debug statement.

**Kind**: instance method of [<code>Command</code>](#Command)  
<a name="Command+getIntent"></a>

### command.getIntent(message) ⇒ <code>boolean</code>
Returns the detected intent of the message.
If there is no "official" intent attached, uses pattern-matching
to determine the intent from the command's list of phrases.

**Kind**: instance method of [<code>Command</code>](#Command)  
**Returns**: <code>boolean</code> - true if intent was detected, false if not  
**Emits**: <code>Intent#event:detected</code>  
**See**: https://botkit.ai/docs/v4/reference/core.html#hears  

| Param | Type |
| --- | --- |
| message | [<code>Message</code>](#Message) | 

<a name="Command+_matchNamedIntent"></a>

### command.\_matchNamedIntent(intent) ⇒ <code>Boolean</code>
Returns true if the intent name matches this intent, false otherwise.

**Kind**: instance method of [<code>Command</code>](#Command)  
**Returns**: <code>Boolean</code> - true if the intent name matches this intent  
**See**: https://stackoverflow.com/a/9436948/154065  

| Param | Type |
| --- | --- |
| intent | <code>String</code> \| <code>Object</code> | 

<a name="Command.getPhraseExpression"></a>

### Command.getPhraseExpression(phrases) ⇒ <code>RegExp</code>
Joins the given phrases into a regular expression.

**Kind**: static method of [<code>Command</code>](#Command)  
**Returns**: <code>RegExp</code> - joined phrases  

| Param | Type | Description |
| --- | --- | --- |
| phrases | <code>Array</code> | The phrases to join |

<a name="Command.matchPhrase"></a>

### Command.matchPhrase(message, phrase) ⇒ <code>boolean</code>
Returns true if the user's message text matches the list of command phrases.

**Kind**: static method of [<code>Command</code>](#Command)  
**Returns**: <code>boolean</code> - true if the user's message matches a known command  

| Param | Type | Description |
| --- | --- | --- |
| message | [<code>Message</code>](#Message) \| <code>string</code> | the user's message or message text |
| phrase | <code>RegExp</code> | the phrase to match |

<a name="IntentConfig"></a>

## IntentConfig : <code>Object</code>
Intent configuration

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| projectId | <code>String</code> | the project ID |
| knowledgeBaseId | <code>String</code> | the knowledge base ID |
| credentials | [<code>CredentialBody</code>](#CredentialBody) | credentials needed to sign into the intent API |

<a name="User"></a>

## User : <code>Object</code>
User data.

Responses sent from the bot are not sent to a particular user,
but to a Webex Teams space. In order to track events
from the [User](#User)'s perspective, we need to internally track user data.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| user_id | <code>String</code> | Encrypted user ID |
| domain | <code>String</code> | Domain of the user, e.g., cisco.com |

<a name="space"></a>

## space : <code>Object</code>
Partial known space data.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| space_id | <code>String</code> | space ID |
| space_type | <code>String</code> | space type, e.g., "direct" or "group" |

<a name="Spaces"></a>

## Spaces : <code>Map</code>
Known spaces.
Keys are of type [Space.space_id](Space.space_id).
Properties are of type [Space](Space).

**Kind**: global typedef  
<a name="UserProp"></a>

## UserProp : <code>Object</code>
Map of user property names and formatting functions.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| name | <code>String</code> | user property name |
| format | <code>function</code> | function to format the user property name |

<a name="MinimalSpace"></a>

## MinimalSpace : <code>Object</code>
The space with the message.
This space has only one property: an ID.

**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| id | <code>String</code> | ID of the space with the message |

<a name="ShouldTrack"></a>

## ShouldTrack : <code>Object</code>
If and why an event should be tracked or not tracked

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| shouldTrack | <code>boolean</code> | true if an event should be tracked, false otherwise |
| reason | <code>String</code> | reason an event is tracked or not tracked |

<a name="MinimalUser"></a>

## MinimalUser : <code>Object</code>
The user (person, bot) receiving a message.
This user has a minimal number of properties.

**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| id | <code>String</code> | ID of the user receiving the message |
| name | <code>String</code> | email of the user receiving the message |

<a name="UserInfo"></a>

## UserInfo : <code>Object</code>
User information for an analytics event

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| user_id | <code>string</code> | user ID |
| user_properties | <code>Object</code> | user properties |
| user_properties.app_environment | <code>string</code> | the app environment, e.g., "development", "staging" |
| user_properties.domain | <code>string</code> | the domain of the user, e.g., "cisco.com" |

<a name="CredentialBody"></a>

## CredentialBody : <code>Object</code>
A Google Auth CredentialBody

**Kind**: global typedef  
**See**

- https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
- https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81

**Properties**

| Name | Type |
| --- | --- |
| client_email | <code>String</code> | 
| private_key | <code>String</code> | 
| project_id | <code>String</code> | 

<a name="IntentConfig"></a>

## IntentConfig : <code>Object</code>
Intent configuration

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| projectId | <code>String</code> | the project ID |
| knowledgeBaseId | <code>String</code> | the knowledge base ID |
| credentials | [<code>CredentialBody</code>](#CredentialBody) | credentials needed to sign into the intent API |

<a name="PhoneNumber"></a>

## PhoneNumber : <code>Object</code>
Person's phone number.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| type | <code>String</code> | type of phone number, e.g., work, home |
| value | <code>String</code> | phone number itself, e.g., '+1 555 867 5309' |

<a name="Person"></a>

## Person : <code>Object</code>
A typical bot user

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| id | <code>String</code> | Encrypted person ID |
| emails | <code>Array.&lt;String&gt;</code> | email addresses |
| phoneNumbers | [<code>Array.&lt;PhoneNumber&gt;</code>](#PhoneNumber) | phone numbers |
| displayName | <code>String</code> | display name |
| nickName | <code>String</code> | nickname |
| firstName | <code>String</code> | first name |
| lastName | <code>String</code> | last name |
| avatar | <code>String</code> | URL of person's avatar at 1600px |
| orgId | <code>String</code> | encrypted organization ID |
| created | <code>Date</code> | date person was created in Webex Teams, e.g., 2014-06-20T20:35:16.172Z |
| type | <code>String</code> | type of user, e.g., "person" |

<a name="People"></a>

## People : <code>Map</code>
Known people.

Keys are of type [Person.id](Person.id).
Properties are of type [Person](#Person).

**Kind**: global typedef  
<a name="WebexPerson"></a>

## WebexPerson : <code>Object</code>
A Webex user

Properties beginning with an underscore denote those
not normally in a Botkit Person object.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| _cecId | <code>String</code> | Cisco Employee Connection ID |
| _cecEmail | <code>String</code> | Cisco Employee Connection email, e.g., cecid@cisco.com |
| _contactType | <code>String</code> | type of contact, e.g., "Cisco" or "Partner" |
| _domain | <code>String</code> | domain name, e.g., cisco.com |
| _roles | <code>Array.&lt;String&gt;</code> | user's roles |

<a name="BridgeConfig"></a>

## BridgeConfig : <code>Object</code>
Configuration options

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| dryRun | <code>boolean</code> | perform a dry run |

<a name="Rollback"></a>

## Rollback : <code>Object</code>
Rollback information

**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| original | <code>String</code> | the original file path |
| backup | <code>String</code> | the backup file path |

<a name="AdaptiveCard"></a>

## AdaptiveCard : <code>Object</code>
Adaptive Card

Adaptive Card based on the [Adaptive Card schema](https://adaptivecards.io/explorer/).

**Kind**: global typedef  
<a name="ChoicesConfig"></a>

## ChoicesConfig
**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| getChoiceTitle | <code>function</code> | determine the title displayed on the UI |
| getChoiceValue | <code>function</code> | determine the value |

<a name="Choice"></a>

## Choice
**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| choice | <code>String</code> | title of the choice as it appears in the UI |
| value | <code>String</code> | value of the choice "behind-the-scenes" |

<a name="CredentialBody"></a>

## CredentialBody : <code>Object</code>
Google Auth CredentialBody

**Kind**: global typedef  
**See**

- https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
- https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81

**Properties**

| Name | Type | Description |
| --- | --- | --- |
| client_email | <code>String</code> |  |
| private_key | <code>String</code> |  |
| project_id | <code>String</code> | project ID (optional) |

<a name="ReleaseConfig"></a>

## ReleaseConfig : <code>Object</code>
Release configuration

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| releasesDir | <code>String</code> | path to a releases directory |

<a name="SalesforceUser"></a>

## SalesforceUser : <code>Object</code>
Salesforce user data.

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| id | <code>String</code> | user ID |
| username | <code>String</code> | username |
| accessToken | <code>String</code> | user's API access token |
| organizationId | <code>String</code> | user's organization ID |
| url | <code>String</code> | full URL after signing in, e.g, https://SUBDOMAIN.my.salesforce.com/id/ORGANIZATION-ID/USER-ID |


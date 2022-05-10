const GoogleConversationalAgent = require("./google");
const { getDownloadCommand, getUploadCommand } = GoogleConversationalAgent;

describe("creates commands", () => {
  it("by default", () => {
    expect(getDownloadCommand).toBeDefined();
    expect(getUploadCommand).toBeDefined();

    expect(getDownloadCommand()).toEqual(
      "gcloud alpha dialogflow agent export --destination=.downloads/conversational-agent.zip"
    );
    expect(getUploadCommand()).toEqual(
      "gcloud alpha dialogflow agent import --source=.releases/conversational-agent.zip"
    );
  });

  it("with options", () => {
    const account = "email@test.com";
    const projectId = "myProjectId";
    const options = { projectId, account };
    expect(getDownloadCommand(options)).toEqual(
      `gcloud alpha dialogflow agent export --account=${account} --destination=.downloads/conversational-agent.zip --project=${projectId}`
    );
  });
});

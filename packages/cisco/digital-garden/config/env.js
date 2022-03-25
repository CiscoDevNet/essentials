const dotenv = require("dotenv");
dotenv.config();

const { Env } = require("@humanwhocodes/env");
const env = new Env();

module.exports = env;

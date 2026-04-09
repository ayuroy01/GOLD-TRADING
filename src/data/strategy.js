import systemRules from "../../gold_v1_system_rules.json";
import mathFoundation from "../../v1_system_and_math_foundation.md?raw";

const stepEntries = Object.entries(systemRules).filter(([key]) =>
  key.startsWith("step_"),
);

export const strategyMeta = systemRules.system_metadata;
export const strategySteps = stepEntries.map(([key, value], index) => ({
  id: key,
  index: index + 1,
  title: key
    .replace(/^step_\d+_/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase()),
  value,
}));

export const noTradeRules = systemRules.step_7_no_trade_conditions;
export const validationPhases = systemRules.validation_phases;
export const systemRulesDocument = systemRules;
export const foundationMarkdown = mathFoundation;

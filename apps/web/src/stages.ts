// Engine stage codes and the plain names the console shows for them.
export const STAGE_NAMES: Record<string, string> = {
  E01: "Load", E02: "GeoIP enrichment", E03: "Value flows", E04: "CoinJoin detection", E05: "Wallet clustering",
  E06: "Change-address model", E07: "Peel chains", E08: "Anomaly model", E09: "Origin IP model", E11: "Co-origin linking",
  E12: "Graph embeddings", E13: "Risk propagation", E14: "Behaviour fingerprints", E15: "Motifs", E16: "Merge suggestions",
  E17: "Lead ranking", E18: "Explanations", E19: "Publish", E20: "Services and victims", E21: "Risk paths", E22: "Actor features",
};

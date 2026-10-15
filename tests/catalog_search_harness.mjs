// Run the website's catalog search over records and queries read from stdin,
// and print each query's ranked record keys. The Python parity test compares
// this output with QueryService over the same records.
import { readFileSync } from "node:fs";
import { searchCatalog } from "../site/assets/catalog-search.js";

const { records, queries } = JSON.parse(readFileSync(0, "utf8"));
const ranked = {};
for (const query of queries) ranked[query] = searchCatalog(records, query).map((record) => record.key);
process.stdout.write(JSON.stringify(ranked));

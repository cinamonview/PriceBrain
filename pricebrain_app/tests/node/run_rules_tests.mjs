/**
 * Firestore Rules tests against running Emulator — docs/05 §6, docs/11 §9.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  doc,
  getDoc,
  setDoc,
} from "firebase/firestore";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, "..", "..", "..");
const rules = readFileSync(join(projectRoot, "firestore.rules"), "utf8");

const testEnv = await initializeTestEnvironment({
  projectId: "demo-pricebrain",
  firestore: {
    rules,
    host: "127.0.0.1",
    port: 8080,
  },
});

let failures = 0;

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    failures += 1;
    console.error(`FAIL ${name}: ${error?.message ?? error}`);
  }
}

await run("catalog read products", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "products", "rules-read"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "products", "rules-read")));
});

await run("catalog read listings", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "listings", "SSG_rules_read"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "listings", "SSG_rules_read")));
});

await run("catalog read gpu_families", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "gpu_families", "GEFORCE_RTX"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "gpu_families", "GEFORCE_RTX")));
});

await run("catalog read board_partners", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "board_partners", "ZOTAC"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "board_partners", "ZOTAC")));
});

await run("catalog read malls", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "malls", "SSG"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "malls", "SSG")));
});

await run("catalog read sellers", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "sellers", "SSG_TEST"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertSucceeds(getDoc(doc(db, "sellers", "SSG_TEST")));
});

for (const [collection, docId] of [
  ["products", "rules-deny-product"],
  ["listings", "SSG_rules_deny"],
  ["gpu_families", "rules-deny-family"],
  ["board_partners", "rules-deny-partner"],
  ["malls", "rules-deny-mall"],
  ["sellers", "rules-deny-seller"],
]) {
  await run(`catalog write deny ${collection}`, async () => {
    const db = testEnv.unauthenticatedContext().firestore();
    await assertFails(setDoc(doc(db, collection, docId), { blocked: true }));
  });
}

await run("price_history client write deny", async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "listings", "SSG_rules_history"), { probe: true });
  });
  const db = testEnv.unauthenticatedContext().firestore();
  await assertFails(
    setDoc(doc(db, "listings", "SSG_rules_history", "price_history", "123"), {
      price: 1,
    }),
  );
});

await run("user own document allow", async () => {
  const db = testEnv.authenticatedContext("user-a").firestore();
  await assertSucceeds(setDoc(doc(db, "users", "user-a"), { displayName: "A" }));
  await assertSucceeds(getDoc(doc(db, "users", "user-a")));
});

await run("user other document deny", async () => {
  const db = testEnv.authenticatedContext("user-a").firestore();
  await assertFails(getDoc(doc(db, "users", "user-b")));
  await assertFails(setDoc(doc(db, "users", "user-b"), { blocked: true }));
});

await run("favorites own allow", async () => {
  const db = testEnv.authenticatedContext("user-a").firestore();
  await assertSucceeds(
    setDoc(doc(db, "users", "user-a", "favorites", "PROD-1"), { added_at: new Date() }),
  );
});

await run("favorites other deny", async () => {
  const db = testEnv.authenticatedContext("user-a").firestore();
  await assertFails(
    getDoc(doc(db, "users", "user-b", "favorites", "PROD-1")),
  );
  await assertFails(
    setDoc(doc(db, "users", "user-b", "favorites", "PROD-1"), { blocked: true }),
  );
});

for (const [collection, docId] of [
  ["crawl_jobs", "SSG_rules_crawl_job"],
  ["crawl_logs", "SSG_rules_crawl_log"],
  ["validation_logs", "rules_validation_log"],
]) {
  await run(`operational write deny ${collection}`, async () => {
    const db = testEnv.unauthenticatedContext().firestore();
    await assertFails(setDoc(doc(db, collection, docId), { blocked: true }));
  });
  await run(`operational read deny ${collection}`, async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await setDoc(doc(ctx.firestore(), collection, docId), { probe: true });
    });
    const db = testEnv.unauthenticatedContext().firestore();
    await assertFails(getDoc(doc(db, collection, docId)));
  });
}

await testEnv.cleanup();

if (failures > 0) {
  console.error(`\n${failures} rule test(s) failed`);
  process.exit(1);
}

console.log("\nAll Firestore rule tests passed");

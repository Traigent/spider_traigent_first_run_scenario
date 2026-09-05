import { describe, expect, it } from "vitest";

import {
  findNetworkTargets,
  findSourceCapabilities,
  readJavaScriptTokens,
} from "../scripts/javascript";

const REMOTE_CALL = 'fetch("https://x.invalid/a");';

describe("javascript lexer", () => {
  it("keeps a fetch on the same line as a JSX closing tag", () => {
    const source = `const a = <div>x</div>; ${REMOTE_CALL}`;
    expect(findSourceCapabilities(source, { jsx: true })).toContain(
      "network capability fetch",
    );
  });

  it("keeps a fetch on the same line as a self-closing JSX tag", () => {
    const source = `const a = <br />; ${REMOTE_CALL}`;
    expect(findSourceCapabilities(source, { jsx: true })).toContain(
      "network capability fetch",
    );
  });

  it("refuses a slash read as a regular expression around a network call", () => {
    const source = `x = function () {} / 2; ${REMOTE_CALL}`;
    const issues = findSourceCapabilities(source);
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatch(
      /^unreadable script: .*regular expression.*network call.* at line 1$/,
    );
    expect(findNetworkTargets(source)).toEqual(issues);
  });

  it("refuses a regular expression with no closing slash on its line", () => {
    const issues = findSourceCapabilities(`return /abc\n${REMOTE_CALL}`);
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatch(/no closing `\/`.* at line 1$/);
  });

  it("refuses a string literal that runs across a line break", () => {
    const issues = findSourceCapabilities(
      `const a = 'it\ns';\n\n${REMOTE_CALL}`,
    );
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatch(/line break.* at line 1$/);
  });

  it("refuses a string literal with no closing quote", () => {
    const issues = findSourceCapabilities(
      'const a = "open; fetch(https://x.invalid/a);',
    );
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatch(/no closing quote/);
  });

  it("reads a backslash line continuation as one string", () => {
    const tokens = readJavaScriptTokens("const a = 'ab\\\ncd';");
    expect(tokens).toContainEqual({ kind: "text", value: "abcd" });
  });

  it("keeps deck copy, escaped addresses and division out of the findings", () => {
    const source = [
      'const copy = "call fetch() at https://example.invalid/";',
      "const remote = /^https?:\\/\\//i;",
      "const ratio = total / count / 2;",
      "const a = <div>x</div>; const b = a / 2;",
      'const markup = `<a href="https://example.invalid/">x</a>`;',
    ].join("\n");
    expect(findSourceCapabilities(source, { jsx: true })).toEqual([]);
    expect(findNetworkTargets(source, { jsx: true })).toEqual([]);
  });

  it("still reads a regular expression after a JSX-free block", () => {
    const tokens = readJavaScriptTokens("if (a) {}\n/x/.test(b);");
    expect(tokens).toContainEqual({ kind: "regular-expression", value: "/x/" });
  });
});

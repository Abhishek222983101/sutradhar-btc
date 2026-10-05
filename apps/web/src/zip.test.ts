import { describe, expect, it } from "vitest";
import { bytes, crc32, readZip, sha256Hex, text, writeZip } from "./zip";

describe("zip", () => {
  it("matches the standard CRC-32 check value", () => {
    expect(crc32(bytes("123456789"))).toBe(0xcbf43926);
  });
  it("writes a zip that reads back to the same files", async () => {
    const files = new Map([["notes.md", bytes("checked the taint path")], ["evidence/1.json", bytes('{"p":0.97}')]]);
    const back = await readZip(writeZip(files));
    expect([...back.keys()].sort()).toEqual(["evidence/1.json", "notes.md"]);
    expect(text(back.get("notes.md")!)).toBe("checked the taint path");
  });
  it("hashes like SHA-256", async () => {
    expect(await sha256Hex(bytes("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});

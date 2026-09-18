import { describe, expect, test, vi } from "vitest";
import { fetchAudioFromAudioItem } from "@/store/audioGenerate";
import type { AudioItem, AudioStoreState, SettingStoreState } from "@/store/type";
import { EngineId, SpeakerId, StyleId, savingSettingSchema } from "@/type/preload";

const irodoriId = EngineId("0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40");

function fixture(engineId = irodoriId) {
  const state = {
    engineManifests: { [engineId]: { defaultSamplingRate: 24000 } },
    engineSettings: { [engineId]: { outputSamplingRate: 24000 } },
    savingSetting: { outputStereo: false },
    experimentalSetting: { enableInterrogativeUpspeak: false },
    enableMemoNotation: true,
    enableRubyNotation: true,
  } as unknown as AudioStoreState & SettingStoreState;
  const audioItem: AudioItem = {
    text: "😊こんにちは！",
    voice: { engineId, speakerId: SpeakerId("確認用"), styleId: StyleId(0) },
    query: {
      accentPhrases: [], speedScale: 1, pitchScale: 0, intonationScale: 1,
      volumeScale: 1, prePhonemeLength: 0.1, postPhonemeLength: 0.1,
      pauseLengthScale: 1, outputSamplingRate: 24000, outputStereo: false,
      kana: "古い文章です。",
    },
  };
  const synthesis = vi.fn(async () => new Blob(["音声"]));
  const instance = {
    invoke: vi.fn(() => synthesis),
  } as unknown as Parameters<typeof fetchAudioFromAudioItem>[1];
  return { state, audioItem, instance, synthesis };
}

describe("IRODORI-VOICE の表現指定", () => {
  test("ステレオ設定を保存済みクエリへ反映し、変更時は再生成する", async () => {
    const { state, audioItem, instance, synthesis } = fixture();
    audioItem.text = "ステレオ出力の確認です。";
    state.savingSetting.outputStereo = savingSettingSchema.parse({}).outputStereo;
    expect(state.savingSetting.outputStereo).toBe(true);
    const stereo = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(stereo.audioQuery.outputStereo).toBe(true);
    expect(audioItem.query?.outputStereo).toBe(false);
    state.savingSetting.outputStereo = false;
    const mono = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(mono.audioQuery.outputStereo).toBe(false);
    expect(synthesis).toHaveBeenCalledTimes(2);
  });

  test("保存済みの古い kana より現在の本文を送り、絵文字の変更で再生成する", async () => {
    const { state, audioItem, instance, synthesis } = fixture();
    const first = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(first.audioQuery.kana).toBe("😊こんにちは！");
    expect(audioItem.query?.kana).toBe("古い文章です。");
    audioItem.text = "😠こんにちは！";
    const second = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(second.audioQuery.kana).toBe("😠こんにちは！");
    expect(synthesis).toHaveBeenCalledTimes(2);
    expect(synthesis).toHaveBeenLastCalledWith(expect.objectContaining({
      audioQuery: expect.objectContaining({ kana: "😠こんにちは！" }),
    }));
  });

  test("メモとルビの設定を反映し、文中の絵文字を保持する", async () => {
    const { state, audioItem, instance } = fixture();
    audioItem.text = "[メモ]今日は😮‍💨{晴天|せいてん}です。";
    const result = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(result.audioQuery.kana).toBe("今日は😮‍💨せいてんです。");
  });

  test("別のエンジンの kana は書き換えない", async () => {
    const { state, audioItem, instance } = fixture(EngineId("別エンジン"));
    const result = await fetchAudioFromAudioItem(state, instance, { audioItem });
    expect(result.audioQuery.kana).toBe("古い文章です。");
  });
});

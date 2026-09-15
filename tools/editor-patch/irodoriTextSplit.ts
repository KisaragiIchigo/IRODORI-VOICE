/**
 * 貼り付けたテキストを行へ割る。IRODORI-VOICE がエディタへ追加するファイル。
 *
 * 本家は「。」の後ろへ一律で改行を入れるため、鉤括弧で囲まれたセリフが途中で切れる。
 * 文の途中で切れた行は単体で合成すると高域が落ちてこもった音になるため、
 * 囲みの中の句点では割らない。
 */

/** 囲みとして扱う括弧。開き括弧から閉じ括弧を引く。 */
const quotePairs = new Map([
  ["「", "」"],
  ["『", "』"],
]);

/**
 * 対応の取れた括弧の範囲を `[開き括弧の位置, 閉じ括弧の位置]` で返す。
 * 閉じ括弧が現れないまま終わった開き括弧は囲みとして扱わない。
 * 閉じ忘れや会話の書き出しだけを貼ったときに、テキスト全体が 1 行へ固まらないようにするため。
 */
const detectQuotedRanges = (text: string): [number, number][] => {
  const ranges: [number, number][] = [];
  const opened: { closeChar: string; index: number }[] = [];

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const closeChar = quotePairs.get(char);
    if (closeChar != undefined) {
      opened.push({ closeChar, index: i });
      continue;
    }
    const innermost = opened.at(-1);
    if (innermost != undefined && char === innermost.closeChar) {
      opened.pop();
      ranges.push([innermost.index, i]);
    }
  }

  return ranges;
};

/**
 * 句点と改行でテキストを分割する。括弧に囲まれた句点では分割しない。
 * 句点や改行が続くと空の要素ができるが、貼り付け側が捨てるためそのまま返す。
 */
export const splitTextByPeriodAndNewLine = (text: string): string[] => {
  const quotedRanges = detectQuotedRanges(text);
  const isQuoted = (index: number) =>
    quotedRanges.some(([start, end]) => start < index && index < end);

  const sentences: string[] = [];
  let sentence = "";
  for (let i = 0; i < text.length; i++) {
    sentence += text[i];
    if (text[i] === "。" && !isQuoted(i)) {
      sentences.push(sentence);
      sentence = "";
    }
  }
  sentences.push(sentence);

  return sentences.flatMap((sentence) => sentence.split(/\r\n|[\r\n]/));
};

import 'dotenv/config';
import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Anthropic from '@anthropic-ai/sdk';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = process.env.PORT || 3000;

if (!process.env.ANTHROPIC_API_KEY) {
  console.warn('警告: ANTHROPIC_API_KEY が設定されていません。.env を確認してください。');
}

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const SYSTEM_PROMPT = `あなたは会話のその場コーチです。ユーザーは友人や気になる相手との会話中に、マイクで拾った直近の発言をあなたに渡します。
あなたの役割は、会話が円滑に、そしてお互いに好意的な印象を持てるように、ユーザーだけに見える短いアドバイスを返すことです。

厳守事項:
- 出力は日本語、最大2文、40〜70文字程度。会話を止めない「耳打ち」レベルの短さに保つこと。
- 直近の会話内容に具体的に触れ、次の一言や態度の提案をすること（例: 相手の話題を掘り下げる質問、共感の相槌、話題転換のタイミングなど）。
- 説教・一般論・長い解説をしない。今すぐ使えるアクションのみ。
- 相手を操作したり誘導したりする狙いのアドバイスではなく、誠実で対等なコミュニケーションを促すこと。
- 特に新しい提案がない、または情報が不足している場合は、無理に助言を作らず "advice" を空文字列にする。
- 必ず以下のJSON形式のみで出力し、他のテキストは一切含めない: {"advice": string, "mood": "good"|"neutral"|"caution"}
  - mood は直近の会話の雰囲気の簡易判定（相手が楽しそうか、間延びしていないか、気まずさがないか）。`;

app.post('/api/advice', async (req, res) => {
  const { recentTranscript, relationship } = req.body || {};

  if (!recentTranscript || typeof recentTranscript !== 'string' || !recentTranscript.trim()) {
    return res.status(400).json({ error: 'recentTranscript is required' });
  }

  try {
    const relationshipLabel =
      relationship === 'romantic_interest' ? '気になっている女性' : relationship === 'friend' ? '友人' : '相手';

    const message = await anthropic.messages.create({
      model: 'claude-sonnet-5',
      max_tokens: 200,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: 'user',
          content: `関係性: ${relationshipLabel}\n直近の会話（文字起こし、複数話者混在の可能性あり）:\n"""\n${recentTranscript.slice(-1500)}\n"""`,
        },
      ],
    });

    const textBlock = message.content.find((block) => block.type === 'text');
    let parsed = { advice: '', mood: 'neutral' };
    try {
      parsed = JSON.parse(textBlock?.text ?? '{}');
    } catch {
      parsed = { advice: '', mood: 'neutral' };
    }

    res.json(parsed);
  } catch (err) {
    console.error('advice generation failed:', err);
    res.status(500).json({ error: 'advice generation failed' });
  }
});

app.listen(port, () => {
  console.log(`Conversation Coach running at http://localhost:${port}`);
});

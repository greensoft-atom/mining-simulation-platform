# 19 · Legal, Compliance and Localization

> **This is not legal advice.** It is an engineering and product checklist that tells us what to ask counsel and what to build. Laws and platform policies change. **Every item marked ⚖ must be confirmed with qualified local counsel** before the market launches, and re-checked before each major release.

## 19.1 Approach

1. Design so that the riskiest categories never apply: no paid randomness, no cash-out, no tradeable items with real-world value, no ads, and minimal personal data.
2. Build compliance into the product (age gate, purchase limits, deletion, odds display, audit), not into documents alone.
3. Launch one market at a time (ADR-002) and review each new market in advance.

## 19.2 Market requirements

| Topic                      | Taiwan (launch)                                                                                                                                                                                                                                                                              | Hong Kong / Macau (soft launch)                                              | Japan (future)                                                                                                                                                                                                                                       | Mudee (future)                                                                                                                                                                     |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Privacy law                | Personal Data Protection Act (個人資料保護法): notice of purposes, categories and rights; security measures; breach notification ⚖                                                                                                                                                           | Personal Data (Privacy) Ordinance (PDPO); Macau Personal Data Protection Act | APPI: purpose specification; cross-border transfer rules                                                                                                                                                                                             | PIPA: strict consent, cross-border disclosure, local representative thresholds ⚖                                                                                                   |
| Online game consumer rules | MOEA **Mandatory and Prohibited Provisions for Online Game Service Standard Contracts** (網路連線遊戲服務定型化契約應記載及不得記載事項). Covers contract terms, rating display, account handling, probability disclosure for paid chance items, and **notice before service termination** ⚖ | General consumer law                                                         | Premiums and Representations Act (景品表示法; kompu-gacha ban, prize value limits on purchase-linked prizes); Specified Commercial Transactions Act notation                                                                                         | Game Industry Promotion Act: **mandatory probability disclosure** for paid chance items (in force since March 2024); recent amendments on domestic agents for foreign publishers ⚖ |
| Game rating                | **Game Software Rating Management Regulations** (遊戲軟體分級管理辦法): 普遍級 / 保護級 / 輔12級 / 輔15級 / 限制級; shown on the store page and in the game ⚖. Expected: 保護級 or 輔12級 (mild fantasy combat, no blood); confirm against the official criteria                             | IARC (through Google Play)                                                   | IARC; CERO not needed for mobile                                                                                                                                                                                                                     | GRAC (self-rating via app stores under agreement)                                                                                                                                  |
| Prepaid currency           | No specific prepaid-instrument regime for game currency known to us ⚖                                                                                                                                                                                                                        | —                                                                            | **Payment Services Act:** if unused _paid_ balance exceeds ¥10M on 31 Mar or 30 Sep → notification + 50% security deposit. Our "paid Aurum spent first" rule ([04 §4.2](04-economy-and-progression.md#42-currencies-and-materials)) reduces exposure | Consumer refund rules for unused currency ⚖                                                                                                                                        |
| Tax                        | Taiwan VAT 5% on e-services. Confirm whether Google Play collects and remits for our sales, or whether we must register as a foreign e-service provider ⚖                                                                                                                                    | No VAT                                                                       | Consumption tax 10% (platform rules) ⚖                                                                                                                                                                                                               | VAT 10% (platform rules) ⚖                                                                                                                                                         |
| Billing                    | Google Play Billing for digital goods                                                                                                                                                                                                                                                        | Same                                                                         | Same (alternative billing programs exist; review)                                                                                                                                                                                                    | **Telecommunications Business Act:** alternative payment options are permitted on stores; review the Play program ⚖                                                                |
| Language                   | Traditional Chinese (Taiwan usage)                                                                                                                                                                                                                                                           | Traditional Chinese acceptable (HK vocabulary differs, see §19.10)           | Japanese required                                                                                                                                                                                                                                    | Mudeen required                                                                                                                                                                    |

**Mainland China is out of scope:**

- NPPA publishing licence (版號) required;
- local operating entity;
- real-name verification and minors' play-time limits;
- data localization;
- no Google Play.

## 19.3 Google Play policy checklist

| Policy area                                 | What we do                                                                                                                                                                              |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Payments**                                | All digital goods (Aurum, Charter, Pass, bundles, cosmetics) use Google Play Billing. No links or prompts to outside payment                                                            |
| **Randomized items**                        | None are sold. If that ever changes: disclose odds before purchase, near the purchase point (policy requirement), plus each market's law (Taiwan, Mudee, Japan) ⚖                       |
| **Subscriptions**                           | Clear price, period, benefits and cancellation path in the store screen; a prepaid plan is also offered; no misleading free-trial copy                                                  |
| **Target API level**                        | Meet the requirement in force at each submission (Play typically raises it yearly, around late August)                                                                                  |
| **16 KB page size**                         | Required for apps targeting Android 15+. Verify Unity and native plugins ([12 §12.11](12-client-architecture.md#1211-build-configuration))                                              |
| **Account deletion**                        | In-app deletion plus a public web deletion page, both linked in the Play Console data-safety form (FR-ACC-007)                                                                          |
| **Data safety form**                        | Declare: account ids, purchase history, app interactions, crash logs, approximate location (country from IP); encryption in transit; deletion available                                 |
| **User-generated content** (chat, names)    | Filters, report and block, moderation, published community rules. Required for apps with UGC                                                                                            |
| **Families / target audience**              | Target audience 13+ (or 16+ ⚖); not designed for children; no Families program participation                                                                                            |
| **Real-money gambling, games and contests** | No real-money anything. The Motherlode Draw gives non-transferable virtual prizes with no purchase (§19.5)                                                                              |
| **Permissions**                             | `INTERNET`, `ACCESS_NETWORK_STATE`, `POST_NOTIFICATIONS` (Android 13+, at runtime when value is clear), `VIBRATE`; billing permission via the library. No location, contacts or storage |
| **Metadata**                                | No misleading screenshots; store art shows real gameplay; zh-TW listing                                                                                                                 |

## 19.4 Terms of Service essentials ⚖

| Clause                          | Content                                                                                                                                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Licence                         | Players get a limited licence to virtual items. Virtual items have **no monetary value** and are not property                                                                      |
| Prohibited conduct              | Cheating, bots, exploits, **real-money trading**, account selling or sharing, harassment                                                                                           |
| Enforcement                     | Warnings, suspensions, bans, and removal of illegitimately obtained items (by ledger reversal); appeal process                                                                     |
| Purchases and refunds           | Through Google Play's policies; our own refund practice ([07 §7.11](07-monetization-and-business-model.md#711-refunds-and-disputes)); Taiwan consumer-law rights preserved         |
| Minors                          | Parental consent for under-18 players; purchase limits                                                                                                                             |
| Draw rules                      | The Motherlode Draw official rules (§19.5) are incorporated by reference                                                                                                           |
| Service changes and termination | Notice period for changes and for ending the service, per Taiwan's standard-contract provisions (commonly cited as ≥ 30 days) ⚖; handling of unused paid currency at termination ⚖ |
| Governing law and disputes      | Taiwan law and courts for Taiwan players ⚖                                                                                                                                         |
| Liability                       | Limits only as far as consumer law allows                                                                                                                                          |

## 19.5 Free draws and prize promotions

Lottery and gambling definitions generally need **prize + chance + consideration**. The Motherlode Draw ([06 §6.5](06-live-operations-and-events.md#65-the-motherlode-draw)) is designed with **no consideration**:

| Safeguard                         | Implementation                                                                                  |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| No purchase can obtain tickets    | Tickets come from gameplay only; the content compiler forbids tickets in store grants           |
| No paid feature increases tickets | Charter, Pass and crates grant no tickets and no multipliers (tested)                           |
| Prizes have no cash value         | Virtual, non-transferable cosmetics and free Aurum; the ToS says so                             |
| Transparent rules                 | Published official rules (eligibility, schedule, odds estimate, selection method, verification) |
| Verifiable fairness               | Commit-reveal + public beacon                                                                   |

Open questions for counsel:

- Is "time and effort" ever treated as consideration in Taiwan or Hong Kong?
- Do we need a prize-promotion filing for virtual prizes?
- Do any future markets require excluding the draw?

## 19.6 Privacy program

- **Privacy policy** in zh-TW and en, linked in the store, on the title screen and in Settings. It covers:
  - what we collect and why (table in [14 §14.10](14-security-and-anti-cheat.md#1410-privacy-and-data-protection));
  - processors: Google Cloud, Firebase Crashlytics and Cloud Messaging, LINE (sign-in only), Google Play;
  - cross-border transfer: primary data in Taiwan (asia-east1), DR replica and backups in Japan (asia-northeast1);
  - retention;
  - rights (access, correction, deletion, export) and how to exercise them;
  - contact.
- **Notice and consent:** the age gate plus a privacy notice at first launch. Push notifications use the runtime opt-in.
- **Data subject requests:** handled in-app and on the web, completed in ≤ 30 days, logged.
- **Breach response:** incident runbook, a counsel-reviewed notification template, notification to affected users and authorities as each law requires ⚖.
- **Records of processing** kept in `/docs/privacy/` (created at M3), reviewed yearly.

## 19.7 Minors and responsible play

| Control             | Value                                                                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Age gate            | Birth year at first launch; cannot be changed later without support                                                                      |
| Under 18            | Monthly purchase limit (Taiwan default NT$3,000; configurable per market); large-purchase confirmation                                   |
| Under 16            | Realm chat off by default (guild chat on); profile visit details limited                                                                 |
| Play-time reminders | Optional "take a break" reminder after 2 h of continuous play                                                                            |
| No pressure design  | No expiring paid offers on permanent items, no fake scarcity, catch-up mechanics ([02 §2.10](02-game-design-document.md#210-objectives)) |

## 19.8 Intellectual property and licences

- **Trademarks:** search "Deepforge" and the zh-TW title in TIPO (Taiwan), the Hong Kong IPD and the main app stores before the M4 store listing. Register in classes 9 and 41 (and 28 if merchandise is planned) ⚖.
- **Original assets:** every art, audio and writing contract includes **assignment of rights** (or an exclusive perpetual licence) and a warranty of originality. Keep source files.
- **Don't copy distinctive expression:** the study warns against copying competitors ([study/04](../study/04-initial-competitor-research.md)). Mechanics are generally not protected, but specific characters, art, names, text and UI layouts can be. Compare final art against the reference games.
- **Open source:** keep a licence inventory (`/docs/legal/third-party.md`). Most libraries are MIT/Apache-2.0; Noto Sans TC is under SIL OFL 1.1 (the licence must be bundled). Add a credits screen in the app. Avoid GPL code in the client.

## 19.9 Cultural and calendar notes

| Topic                               | Guidance                                                                                                                                                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Numbers                             | **8** (八, sounds like 發 "prosper") is lucky: use 8 / 88 / 888 in rewards and milestones. **4** (四 sounds like 死 "death") should be avoided in celebratory counts, tier names and gift amounts. 6 (六六大順) and 9 are positive |
| Colors                              | Red and gold are festive and lucky. White (and black) relate to funerals: avoid white envelopes or white-themed gifts in festive events                                                                                            |
| Ghost Month (鬼月, 7th lunar month) | Avoid launches and big "new beginning" campaigns. Mild spooky cosmetics are fine                                                                                                                                                   |
| Lunar New Year                      | The biggest event. Red envelopes (紅包) with auspicious amounts. Spending peaks around it                                                                                                                                          |
| Politics                            | Stay neutral: no flags, sovereignty maps or political symbols; National Day (10/10) gets neutral content or none                                                                                                                   |
| Tone                                | Friendly, light humor. Address the player as 你 (casual, standard in games). Avoid crude internet slang in system text                                                                                                             |
| Typography                          | Full-width punctuation (，。！？「」); quotes use 「」 and 『』; no spaces between Chinese characters                                                                                                                              |
| Numbers display                     | 萬/億 for large numbers (1.24萬); dates as 2026/11/02                                                                                                                                                                              |
| Names                               | Allow CJK and Latin, 2–12 characters counted by grapheme; disallow zero-width and control characters; NFKC normalization for uniqueness                                                                                            |

## 19.10 Localization process

| Step                           | Detail                                                                                                                                                                                                                                                              |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source language                | English for development strings, zh-TW as the primary shipped language. Writers may author directly in zh-TW for story and marketing                                                                                                                                |
| String freeze                  | 2 weeks before each client release; content strings (events, items) follow the content pipeline and can ship without a client release                                                                                                                               |
| Context                        | Each key carries `context` and `max_length` columns plus a screenshot link ([15 §15.2](15-content-pipeline-and-admin-tools.md#152-source-format))                                                                                                                   |
| Glossary                       | Fixed terminology ([Appendix A](appendices/A-glossary.md) zh-TW column), enforced in review                                                                                                                                                                         |
| LQA                            | A native Taiwanese reviewer checks every string in context (screenshots + build) before M4 and for each release                                                                                                                                                     |
| Taiwan vs Hong Kong vocabulary | Same script, different words. Examples: software 軟體 (TW) / 軟件 (HK); video 影片 / 視頻; quality 品質 / 質素 (HK colloquial); network 網路 / 網絡. The soft launch in HK uses TW copy (acceptable); add an HK-variant table only if launching HK as a full market |
| Avoid conversion artifacts     | Never machine-convert Simplified to Traditional; the vocabulary differs (e.g. 質量→品質, 數據→資料, 視頻→影片)                                                                                                                                                      |
| Pseudo-localization            | Expansion +30% and bracket wrapping in CI screenshots (NFR-LOC-001)                                                                                                                                                                                                 |

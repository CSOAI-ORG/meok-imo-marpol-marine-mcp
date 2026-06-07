<!-- mcp-name: io.github.CSOAI-ORG/meok-imo-marpol-marine-mcp -->
[![MCP Scorecard: 90/100](https://img.shields.io/badge/proofof.ai-90%2F100-5b21b6)](https://proofof.ai/scorecard/meok-imo-marpol-marine-mcp.html)

# meok-imo-marpol-marine-mcp

> IMO MARPOL + marine fuel + container ship compliance MCP. MARPOL Annex VI, EU ETS maritime, CII, EEXI, IMDG, bunker fuel, ballast water, Port State Control inspection prep. By **MEOK AI Labs**.

## Why this exists

MEOK started with road haulage. Maritime is the next vertical — short-sea operators (RoRo car carriers, Channel freight), container shipping, and the marine fuel cliff for net-zero. 2026 is the year the bills come due: EU ETS maritime is biting, CII/EEXI ratings are public, and the 2030 GHG step-change is closer than most fleet managers think.

Real cliffs this MCP exists to help operators clear:
- **MARPOL Annex VI 0.5% sulfur cap** (global, Jan 2020) + **0.1% in ECAs** (North Sea, Baltic, North America). Fines up to USD 250k + vessel detention by Port State Control.
- **EU ETS maritime** (Jan 2024) — 50% of intra-EU + 100% of intra-EU voyages carbon-priced. 2026 ramp: 70% of allowances surrendered (vs 40% in 2024).
- **CII annual rating** (since Jan 2023) — A/B/C/D/E. Three consecutive D or one E = corrective action plan required.
- **IMDG Code** — Class 9 lithium batteries on container ships (Felicity Ace 2022, Fremantle Highway 2023 — 4,000+ vehicles lost combined).
- **IMO Ballast Water Management Convention** (2017) — D-2 standard rollout completing 2024-2025.
- **Port State Control** detention rates: Paris MoU 3.4% (2024), Tokyo MoU 3.1%. Each detention = 24-72h vessel delay = USD 30-100k.

## Install

```bash
pip install meok-imo-marpol-marine-mcp
```

## Tools (8)

| Tool | Use case |
|------|----------|
| `check_marpol_annex_compliance` | MARPOL Annex VI sulfur cap (0.5% global / 0.1% ECA) |
| `check_eu_ets_maritime` | EU ETS extension to shipping, 50% intra-EU emissions |
| `check_imo_ccc_carbon_intensity` | CII annual rating A-E since Jan 2023 |
| `check_eexi_efficiency` | Energy Efficiency Existing Ship Index (EEXI) ratings |
| `check_imdg_code_dangerous_goods` | IMDG Code for sea-borne dangerous goods (Class 9 li-ion) |
| `check_bunker_compliance` | Sulfur/NOx/PM bunker fuel test vs BDN |
| `check_ballast_water_management` | IMO BWM Convention 2017+ D-2 standard |
| `prepare_psc_inspection_pack` | Port State Control prep (Paris MoU / Tokyo MoU) |

## Pricing

- **Free** — MIT self-host
- **Starter** — £149/mo (MARPOL + EU ETS reporting + CII tracking)
- **Pro** — £399/mo (multi-vessel, EEXI + IMDG + bunker + ballast + PSC pack)
- **Fleet** — £1,999/mo (15+ vessels, charter party, voyage optimisation API, SSO)

Marine is the premium vertical — single PSC detention costs more than a year of the Fleet tier.

## Regulatory basis

- IMO MARPOL (International Convention for the Prevention of Pollution from Ships)
- MARPOL Annex VI (air pollution + GHG)
- IMO CII / EEXI Resolutions MEPC.336(76) and MEPC.337(76)
- EU ETS Directive 2003/87/EC (extended to maritime, Directive (EU) 2023/959)
- IMDG Code (International Maritime Dangerous Goods Code)
- IMO Ballast Water Management Convention 2004 (in force 2017)
- Paris MoU + Tokyo MoU on Port State Control

## License

MIT (c) 2026 Nicholas Templeman / MEOK AI Labs · [haulage.app](https://haulage.app)


## Configuration

Add to your `claude_desktop_config.json` (Claude Desktop) or your MCP client config:

```json
{
  "mcpServers": {
    "meok-imo-marpol-marine-mcp": {
      "command": "uvx",
      "args": ["meok-imo-marpol-marine-mcp"]
    }
  }
}
```

Or: `pip install meok-imo-marpol-marine-mcp` then run the `meok-imo-marpol-marine-mcp` command (stdio transport).

## Examples

Once configured, ask your assistant, for example:
- "Use `check_marpol_annex_compliance` to …"
- "Use `check_eu_ets_maritime` to …"
- "Use `check_imo_ccc_carbon_intensity` to …"


<!-- GEO-FOOTER:v1 -->

---

### Part of the MEOK constellation

This MCP is one node in a connected ecosystem built by **MEOK AI LABS** around a single
sovereign AI core — governed agents with a hash-chained audit trail, mapped to the CSOAI
compliance charter.

- 🌐 The whole map: **<https://meok.ai/constellation>**
- 🛡️ AI governance & certification: **<https://councilof.ai>** · **<https://csoai.org>**
- ✅ Verify any signed report: **<https://meok.ai/verify>**

# Budget Evidence for Mirsad: Verified 2026 Prices and a Revised Budget

*Research track: budget-evidence. Mirsad (مرصاد) IS499 Senior Project, Prince Sultan University, 2026-2027. Compiled 11 October 2026.*

## Introduction

The Senior Project Approval Proposal (SPAP) set a budget of 1,660 SAR in five lines: LLM API usage (750), a cloud VM (600), Google Play registration (100), domain and TLS (60), and contingency (150). Two design decisions made since then change what the project needs to buy. First, development and most of the evaluation now run on local open-weight models served by Ollama. Second, the human-in-the-loop approval client is a Progressive Web App (PWA) instead of store-distributed native apps. This track collects the official, current price pages behind every budget line so the revised budget can be defended line by line. All prices were read from the vendor's own page (or an official registry or central-bank page) on 11 October 2026. They are quoted in the vendor's currency exactly as shown and converted to Saudi riyals at the official peg of 3.75 SAR per USD [1]. Unless a page says otherwise, the prices exclude taxes such as VAT and exclude card or foreign-exchange fees. The contingency line covers those.

**How the sources were checked.** Every price was read from the live page, either through a page fetch or by downloading the raw HTML and searching it for the exact figure. This second check was used on pages that render their tables with JavaScript (OpenAI, Hetzner, DigitalOcean, AWS, Porkbun, Sahara Net) and on figures released after the compiler's training data, such as the GPT-6 and Claude 5.5 model names. Where a page did not state a detail, the detail is left out rather than guessed. For example, the SaudiNIC regulations set no price for .sa names, so the .sa price comes from a licensed registrar instead. Several third-party price trackers and blogs came up in searches. They are not cited, but they helped locate the official pages.

**Token model used for the LLM estimate.** The task assumes about 2,000 benchmark episodes of about 6,000 tokens each, or 12 million billed tokens per model per full run. Agent episodes resend tool outputs and conversation history on every turn, so they are input-heavy. The base case therefore assumes 5,000 input and 1,000 output tokens per episode (10M input + 2M output per run). Two sensitivity cases are reported: an output-heavier split (4,000 input / 2,000 output, which allows for reasoning tokens) and the tokenizer effect described in [2].

---

## A. Currency conversion

### [1] Saudi Central Bank (SAMA): the riyal-dollar peg

**Reference.** Saudi Central Bank (SAMA), "SAMA Affirms Commitment to Exchange Rate Policy," SAMA Media Center, 2020. [Online]. Available: https://www.sama.gov.sa/en-US/MediaCenter/News/Pages/news-557.aspx. Accessed: Oct. 11, 2026.

**Summary.** In this statement, the Saudi central bank restates its policy of pegging the riyal to the US dollar. It commits to keeping the rate at the official 3.75 riyals per dollar. It presents the peg as an anchor for monetary and financial stability and points to the size of the Kingdom's foreign-exchange reserves as backing. The page is dated 5/4/2020. The day-month order of that date is ambiguous, so only the year is cited here.

**Strengths and limitations.** It is the primary, official source for the conversion rate, which is better than a commercial FX quote. It is a policy statement from 2020, not a daily rate feed. Card issuers also add their own conversion or foreign-transaction fees on top of the peg.

**Relevance to Mirsad.** Every SAR figure in this document is the USD price × 3.75. Because the rate is a fixed peg, USD prices convert into SAR without exchange-rate risk. That is why the revised budget prefers USD-billed options, and why Hetzner is priced from its USD column instead of its EUR column.

---

## B. LLM API usage

### [2] Anthropic: Claude API pricing

**Reference.** Anthropic, "Pricing," Claude Platform Docs. [Online]. Available: https://platform.claude.com/docs/en/about-claude/pricing. Accessed: Oct. 11, 2026.

**Summary.** The page lists per-million-token (MTok) prices for every Claude model, with separate columns for base input, cache writes, cache hits and output. Claude Sonnet 5.5 is listed at $2 / MTok input and $10 / MTok output, and cache hits cost $0.10 / MTok. The Batch API halves both rates, so Sonnet 5.5 costs $1 / MTok input and $5 / MTok output when run asynchronously. The page also notes that Claude 4.7 and later models use a newer tokenizer that produces approximately 30% more tokens for the same text than the previous Claude tokenizer (used by Claude Sonnet 4.6 and earlier). Other sections cover tool-use overhead, including a small fixed tool-use system prompt (286 tokens for Sonnet 5.5 with `tool_choice` auto or none).

**Strengths and limitations.** It is the authoritative first-party price list, with batch and caching discounts that matter for a benchmark. All prices are in USD. The page does not say how tax applies to direct Claude API purchases; it mentions tax only for the AWS and Azure Marketplace billing routes ("Pre-tax metering"). The 30% figure compares Claude's new tokenizer with its old one, not with other vendors' tokenizers, so applying it to a "6k-token" episode is a planning allowance rather than a measured difference; the real count should be measured with Anthropic's token-counting endpoint.

**Relevance to Mirsad.** Sonnet 5.5 is the Anthropic mid-tier model chosen for the confirmatory cloud run. Base case per full run: 10M × $2 + 2M × $10 = **$40 (150 SAR)**, or **$20 (75 SAR)** through the Batch API. With the 30% tokenizer allowance, the base case rises to about $52 (195 SAR). The tool-use overhead line is a reminder that Mirsad's tool schemas add input tokens to every turn.

### [3] Anthropic: models overview (positioning of Sonnet 5.5)

**Reference.** Anthropic, "Models overview," Claude Platform Docs. [Online]. Available: https://platform.claude.com/docs/en/models/overview. Accessed: Oct. 11, 2026.

**Summary.** The page compares the current Claude line-up: Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5. It describes Sonnet 5.5 as the model that best combines speed and intelligence, and gives its API ID (`claude-sonnet-5-5`), a 1M-token context window, 128K maximum output and $2 / $10 per MTok pricing. It notes that every current model supports tool use. It also lists a retirement commitment of no sooner than 28 September 2027 for Sonnet 5.5 on Anthropic-operated platforms (Amazon Bedrock and Google Cloud set their own dates).

**Strengths and limitations.** It confirms that Sonnet 5.5 sits in the middle of the line-up, both in price (between Haiku 5.5 and Opus 5.5) and in positioning. The retirement date matters for reproducibility: the model should still be served when the project is examined in 2027. The page gives no benchmark scores, so "mid-tier" here describes price and positioning only.

**Relevance to Mirsad.** It justifies naming Sonnet 5.5 as the Anthropic "mid-tier model" in the budget. It also confirms that a pinned model ID will stay available through the end of the 2026-2027 academic year.

### [4] Anthropic: how API credits are bought

**Reference.** Anthropic, "How do I pay for my Claude API usage?," Claude Help Center. [Online]. Available: https://support.claude.com/en/articles/8977456. Accessed: Oct. 11, 2026.

**Summary.** The article explains that Claude API usage is paid from prepaid credits bought in the Console by a user with an admin or billing role. Credits can be used as soon as they are bought, and an optional auto-reload can top them up at a chosen threshold. Purchased credits expire one year after purchase, the date cannot be extended, and purchases are non-refundable. The article does not state a minimum purchase amount.

**Strengths and limitations.** It is the official billing policy and it is short and unambiguous. It does not cover taxes or the minimum top-up, which have to be checked in the Console when buying.

**Relevance to Mirsad.** Credits cannot be refunded, so the team should buy them just in time, right before the confirmatory run, and not at the start of the year. Auto-reload should stay off so that a runaway agent loop cannot overspend the budget.

### [5] OpenAI: API pricing

**Reference.** OpenAI, "Pricing," OpenAI API Docs. [Online]. Available: https://developers.openai.com/api/docs/pricing. Accessed: Oct. 11, 2026.

**Summary.** The page lists per-1M-token prices by processing tier (Standard, Batch, Flex, Fast, Ultrafast). Each tier has columns for input, cached input, cache writes and output, with separate short-context (≤272K input tokens) and long-context prices. In the "flagship models" table, the middle model, `gpt-6.1-sol`, costs $2.00 input / $0.10 cached input / $2.50 cache writes / $10.00 output per 1M tokens on Standard short context. On Batch it costs $1.00 / $0.05 / $1.25 / $5.00. A tooltip states that output prices include reasoning tokens even though those tokens are not shown in the API response.

**Strengths and limitations.** It is the authoritative first-party source and makes the cost of reasoning tokens explicit. The page lists many model generations and records recent changes (for example, it notes that Priority processing was renamed Fast mode on 30 July 2026). It gives no date of its own, so the access date must always be cited.

**Relevance to Mirsad.** `gpt-6.1-sol` is the OpenAI mid-tier model for the confirmatory run on the OpenAI-style function-calling path. Base case per full run: 10M × $2 + 2M × $10 = **$40 (150 SAR)**, or **$20 (75 SAR)** on Batch. The output-heavier case (4k in / 2k out) costs $56 (210 SAR). Because reasoning tokens bill as output, the 4k/2k case is the realistic planning figure when reasoning is enabled.

### [6] OpenAI: models page (positioning of GPT-6.1 Sol)

**Reference.** OpenAI, "Models," OpenAI API Docs. [Online]. Available: https://developers.openai.com/api/docs/models. Accessed: Oct. 11, 2026.

**Summary.** The page presents three current models. GPT-6 Astra is the most capable and most expensive model. GPT-6.1 Sol is the balanced option, offering performance close to Astra at a lower cost. GPT-6 Luna is the efficient model for high-volume work. For GPT-6.1 Sol, the listed tools include function calling ("Functions"), web search, file search and computer use, with reasoning effort levels from low to max.

**Strengths and limitations.** It confirms that GPT-6.1 Sol is the mid-tier model and that it supports function calling, which Mirsad's OpenAI-style adapter needs. Like any vendor page, it presents the models favourably and gives no independent measurements.

**Relevance to Mirsad.** It justifies choosing `gpt-6.1-sol` as the OpenAI counterpart to Claude Sonnet 5.5. The two models have identical list prices ($2 / $10), so cost differences between them come from token counts, not from pricing.

### [7] Ollama: open-source local model runtime

**Reference.** Ollama, "ollama/ollama," GitHub repository, MIT License. [Online]. Available: https://github.com/ollama/ollama. Accessed: Oct. 11, 2026.

**Summary.** Ollama is an open-source runtime that downloads open-weight models and serves them on the user's own machine through a REST API. The repository is released under the MIT license. It is actively maintained: the latest release when checked was v0.40.3, published on 11 October 2026. Running models locally carries no Ollama licence or usage fee. The cost is the team's own hardware and electricity.

**Strengths and limitations.** It removes per-token cost entirely, keeps benchmark data on the team's machines, and makes runs repeatable offline. The MIT licence covers the Ollama software only; each model's weights carry their own licence, which should be checked before results are published. Local models are smaller and usually weaker than the cloud mid-tier models. Results from them therefore need at least one cloud-model run for comparison. Throughput depends on the team's laptops or lab GPUs. (Ollama also offers a hosted cloud API, documented on the compatibility page [8]. It is not used or budgeted here, and its pricing page could not be reached from the research environment.)

**Relevance to Mirsad.** This is the design decision that cuts the LLM line. All development, debugging and most of the 2,000-episode evaluation run on Ollama at 0 SAR. Paid API calls are kept for one confirmatory run per cloud provider.

### [8] Ollama: OpenAI-compatible API

**Reference.** Ollama, "OpenAI compatibility," Ollama Docs. [Online]. Available: https://docs.ollama.com/api/openai-compatibility. Accessed: Oct. 11, 2026.

**Summary.** The page documents that Ollama exposes a subset of the OpenAI API, including `/v1/chat/completions`. Tool (function) calling is marked as supported for chat completions and for the Responses-style endpoint. The same client code can therefore talk to a local model or to OpenAI by changing the base URL and model name.

**Strengths and limitations.** It makes "develop locally, confirm in the cloud" cheap to implement, because Mirsad's OpenAI-style adapter needs no second code path. The compatibility is only partial, so features outside the documented subset must be checked one by one.

**Relevance to Mirsad.** It shows that the local-first plan is technically feasible. The gateway intercepts the same function-calling message format whether the backend is Ollama or `gpt-6.1-sol`, so local results and cloud results come from the same pipeline.

---

## C. Cloud VM for the demo gateway (2 vCPU, 4 GB RAM)

### [9] Hetzner: June 2026 price adjustment (official price table)

**Reference.** Hetzner Online GmbH, "Hetzner Price Adjustment 15 June 2026," Hetzner Docs, ID GE-D9256, Jun. 15, 2026 (last changed Jul. 8, 2026). [Online]. Available: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/. Accessed: Oct. 11, 2026.

**Summary.** This official notice lists old and new hourly and monthly prices, excluding IPv4 and excluding VAT, for Hetzner dedicated and cloud products, by location. The new prices apply to new orders and cloud instance rescales from 15 June 2026. For Germany/Finland, the shared-vCPU CX23 (2 vCPU, 4 GB) went from €3.99 to €5.49 per month (USD column: $4.99 to $6.49). The AMD CPX22 (2 vCPU, 4 GB, 80 GB) went from €7.99 to €19.49 per month (USD: $9.49 to $22.99). The increases vary widely between product lines: in the Germany/Finland EUR column, about 1.3× to 1.4× for the CX and CAX plans (1.38× for CX23) and about 2.4× to 2.8× for the CPX plans (2.44× for CPX22).

**Strengths and limitations.** It is the provider's own price table, with a USD column that converts cleanly through the SAR peg. It shows that cloud prices changed sharply within 2026, and it excludes the IPv4 add-on [10] and VAT.

**Relevance to Mirsad.** Monthly cost including IPv4 [10]: CX23 = $6.49 + $0.60 = $7.09 (26.59 SAR), or 159.53 SAR for 6 months. CPX22 = $22.99 + $0.60 = $23.59 (88.46 SAR), or 530.78 SAR for 6 months. The sharp June 2026 increases are documented evidence for keeping a contingency line.

### [10] Hetzner: IP pricing

**Reference.** Hetzner Online GmbH, "IP pricing," Hetzner Docs (last changed Apr. 13, 2023). [Online]. Available: https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/. Accessed: Oct. 11, 2026.

**Summary.** The page lists Hetzner's IP address charges. A primary IPv4 address for a cloud server costs €0.50 per month ($0.60), excluding VAT, and primary IPv6 is free.

**Strengths and limitations.** It is official and short. It has not changed since 2023, so it should be checked again at the time of purchase.

**Relevance to Mirsad.** A demo gateway needs a public IPv4 address so that any phone can reach the PWA, so the $0.60 per month is added to Hetzner's server price.

### [11] Hetzner: cloud product pages (current availability)

**Reference.** Hetzner Online GmbH, "Cheap cloud-hosting – low vps prices for developers" (Cost-Optimized plans) and "Hetzner Virtual Private Server: Best Price-Performance Ratio" (Regular Performance plans). [Online]. Available: https://www.hetzner.com/cloud/cost-optimized/ and https://www.hetzner.com/cloud/regular-performance/. Accessed: Oct. 11, 2026.

**Summary.** The Cost-Optimized page lists eight CX and CAX plans, including CX23 (2 Intel/AMD vCPU, 4 GB, 40 GB NVMe). On 11 October 2026 every one of them was labelled "not available". The Regular Performance page lists the CPX plans, including CPX22 (2 AMD vCPU, 4 GB, 80 GB NVMe), without that label. Both pages mark their displayed prices "Price incl. IPv4". The price figures themselves load through JavaScript and did not appear in the page source.

**Strengths and limitations.** It is the only official evidence of whether a plan can be ordered right now, which the price table [9] does not show. Availability changes often, so this is a snapshot of one day.

**Relevance to Mirsad.** The cheapest option on paper (CX23, about 160 SAR for 6 months) cannot be ordered today. The budget therefore uses the price of a plan that can be ordered (about 540 SAR) and treats CX23 as a possible saving.

### [12] DigitalOcean: Droplet pricing

**Reference.** DigitalOcean, "Droplet Pricing." [Online]. Available: https://www.digitalocean.com/pricing/droplets. Accessed: Oct. 11, 2026.

**Summary.** The page lists Basic Droplet plans with a monthly cap and an hourly rate. The 4 GiB / 2 vCPU plan includes 80 GiB SSD and 4,000 GiB transfer for $24.00 per month ($0.03571 per hour). The page also announces that Droplets moved to per-second billing on 1 January 2026, with a 60-second (or $0.01) minimum, and that bundled plans never cost more than their monthly price.

**Strengths and limitations.** The price is flat, in USD, and includes a public IPv4 address and generous transfer. Per-second billing makes short-lived test servers cheap. It costs more than Hetzner's CX23, and DigitalOcean is no longer in the GitHub Student Developer Pack [26], so there is no student credit.

**Relevance to Mirsad.** $24 × 6 months = $144 = **540 SAR**. This is the reference price for the revised VM line. Per-second billing also supports a cheaper option: turn the server on only around testing and demo windows.

### [13] Amazon Web Services: Lightsail pricing

**Reference.** Amazon Web Services, "Amazon Lightsail Pricing." [Online]. Available: https://aws.amazon.com/lightsail/pricing/. Accessed: Oct. 11, 2026.

**Summary.** Lightsail sells fixed monthly Linux/Unix bundles. The general-purpose bundle with 4 GB memory, 2 vCPUs, 80 GB SSD and 4 TB transfer costs $24 per month with a public IPv4 address, or $20 per month as an IPv6-only bundle. The page mentions a free-tier entry offer but does not say which bundles it covers.

**Strengths and limitations.** It is a third independent price point that matches DigitalOcean's, which supports $24 per month as a market price for this size. The IPv6-only bundle is cheaper, but some mobile and campus networks still lack IPv6, so it is not suitable for a public demo.

**Relevance to Mirsad.** $24 × 6 = 540 SAR (IPv4), or $20 × 6 = 450 SAR (IPv6 only). It confirms the 540 SAR planning figure.

---

## D. Domain name and TLS

### [14] Porkbun: domain name pricing (.com)

**Reference.** Porkbun, "Domain Name Pricing." [Online]. Available: https://porkbun.com/products/domains. Accessed: Oct. 11, 2026.

**Summary.** Porkbun, an ICANN-accredited registrar, publishes a full table of registration, renewal and transfer prices in USD. Its notes say that prices include ICANN and other fees. A .com name costs $11.08 to register, $11.08 to renew and $11.08 to transfer, for one year each.

**Strengths and limitations.** The registration and renewal prices are the same, so there is no first-year discount followed by a higher renewal, and the price includes the ICANN fee. It is one registrar's retail price, and other registrars charge more or less.

**Relevance to Mirsad.** A .com costs $11.08 = **41.55 SAR per year**. A stable name gives the PWA a fixed HTTPS origin. Push subscriptions and installed web apps are tied to that origin, so the name should not change during the project.

### [15] SaudiNIC (CST): Saudi Domain Names Registration Regulations

**Reference.** Communications, Space & Technology Commission (SaudiNIC), "Saudi Domain Names Registration Regulations," ver. 5.0, Feb. 2024. [Online]. Available: https://nic.sa/en/help/regulation. Accessed: Oct. 11, 2026.

**Summary.** The regulations set who may register Saudi names. Eligible registrants include entities located in the Kingdom, natural persons with Saudi nationality or Premium Residency, holders of Saudi licences, and owners of Saudi-registered trademarks. Second-level .sa names are open to any eligible person or entity. Zones such as .com.sa, .edu.sa and .med.sa require a commercial registration or a sector licence, and pub.sa is reserved for individuals. The regulations allow fees to be imposed but contain no price list.

**Strengths and limitations.** It is the primary legal source on eligibility. It does not give prices, so a registrar's price list is needed [17].

**Relevance to Mirsad.** A team member with Saudi nationality could register a plain .sa name (not .edu.sa, which is reserved for licensed institutions). A .sa name would suit a bilingual Arabic/English security product, but it is optional.

### [16] SaudiNIC: list of licensed registrars

**Reference.** SaudiNIC, "Registrars." [Online]. Available: https://nic.sa/en/registrars. Accessed: Oct. 11, 2026.

**Summary.** The page lists the registrars licensed to sell Saudi names to non-government customers: Hawsabah, Solutions, NourNet, Sahara Net, DNet and T2. A separate DGA platform handles government domains. The registry's home page says that new non-government registrations go only through these licensed registrars.

**Strengths and limitations.** It is official and shows which retail prices count as legitimate .sa prices. It gives no prices itself.

**Relevance to Mirsad.** It confirms that Sahara Net [17] is a licensed registrar, so its .sa price is a valid budget reference.

### [17] Sahara Net: domain pricing (.sa)

**Reference.** Sahara Net, "Domain Pricing." [Online]. Available: https://shop.sahara.com/index.php?rp=/domain/pricing. Accessed: Oct. 11, 2026.

**Summary.** The registrar's price table gives a new-registration, transfer and renewal price for each extension. For .sa (and .com.sa, .pub.sa, .net.sa and others) the table shows SAR 52.18 for a new one-year registration, SAR 52.18 for a transfer and SAR 86.09 for a one-year renewal. The same table lists .com at SAR 75.00 for each operation. The page does not say whether these prices include VAT.

**Strengths and limitations.** The prices are in SAR from a licensed Saudi registrar, so no currency conversion is needed. Renewal costs more than the first year, and the VAT treatment is not stated.

**Relevance to Mirsad.** An optional .sa name costs **52.18 SAR** in year one, about 10 SAR more than the Porkbun .com. Porkbun's .com is cheaper than Sahara Net's own .com price (75 SAR), which is why the budget uses Porkbun for .com.

### [18] Let's Encrypt: about the CA

**Reference.** Internet Security Research Group, "About Let's Encrypt" and "FAQ," Let's Encrypt. [Online]. Available: https://letsencrypt.org/about/ and https://letsencrypt.org/docs/faq/. Accessed: Oct. 11, 2026.

**Summary.** Let's Encrypt describes itself as a free, automated and open certificate authority run by the non-profit Internet Security Research Group (ISRG). Anyone who owns a domain can get a trusted certificate at no charge. Certificates are issued and renewed automatically through an open protocol published as a standard (ACME, RFC 8555). All issued or revoked certificates are publicly recorded.

**Strengths and limitations.** It removes the TLS cost entirely and is supported by standard tooling (Caddy, Certbot, Traefik). The FAQ states that it issues Domain Validation (DV) certificates only, with no plans for OV or EV, and that it cannot offer direct support to subscribers (help comes from community forums and documentation). Renewal must be automated.

**Relevance to Mirsad.** TLS costs **0 SAR**. HTTPS is not optional, because the PWA's service worker only runs in a secure context [21].

### [19] McPherrin (2025): decreasing certificate lifetimes to 45 days

**Reference.** M. McPherrin, "Decreasing Certificate Lifetimes to 45 Days," Let's Encrypt, Dec. 2, 2025. [Online]. Available: https://letsencrypt.org/2025/12/02/from-90-to-45. Accessed: Oct. 11, 2026.

**Summary.** The post announces a phased reduction in certificate lifetimes from the current 90 days. The opt-in `tlsserver` profile was scheduled to start issuing 45-day certificates on 13 May 2026. The default `classic` profile moves to 64-day certificates (with a 10-day authorization-reuse period) on 10 February 2027 and to 45-day certificates (with a 7-hour authorization-reuse period) on 16 February 2028. The aim is to meet the CA/Browser Forum Baseline Requirements. The post also says that renewing at a hard-coded 60-day interval will no longer be sufficient.

**Strengths and limitations.** It is an official timeline from the CA. It concerns operations, not cost: the certificates stay free.

**Relevance to Mirsad.** The 64-day default takes effect during the project year, in February 2027. The deployment must therefore renew certificates automatically (ideally with ACME Renewal Information) and not on a fixed 60-day timer.

### [20] McPherrin (2026): 6-day and IP-address certificates

**Reference.** M. McPherrin, "6-day and IP Address Certificates are Generally Available," Let's Encrypt, Jan. 15, 2026. [Online]. Available: https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability. Accessed: Oct. 11, 2026.

**Summary.** Let's Encrypt made two features generally available: short-lived certificates valid for 160 hours, and certificates for IPv4 and IPv6 addresses. Both are requested through the opt-in "shortlived" profile, and IP-address certificates are only issued as short-lived certificates.

**Strengths and limitations.** It lets a server with a public IP address serve trusted HTTPS without owning any domain. Six-day certificates require reliable automation, and an address-based URL is hard to remember and changes if the server is replaced.

**Relevance to Mirsad.** It supports the zero-cost fallback: a VM's public IP address can serve the PWA over trusted HTTPS with no domain purchase.

### [21] MDN: Service Worker API (secure-context requirement)

**Reference.** MDN contributors, "Service Worker API," MDN Web Docs, Mozilla. [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API. Accessed: Oct. 11, 2026.

**Summary.** MDN's reference explains that service workers act as a programmable proxy between a web app and the network, which enables offline use, push messages and background sync. It states that service workers are only available in secure contexts, meaning pages served over HTTPS, with `http://localhost` treated as secure for development.

**Strengths and limitations.** It is a widely used, well-maintained reference. It is documentation, not the normative W3C specification.

**Relevance to Mirsad.** It explains why the budget cannot drop TLS or a reachable HTTPS origin. A phone approving tool calls is never `localhost`, so the approval PWA and its web-push channel need a real HTTPS endpoint.

---

## E. App stores the PWA avoids

### [22] Google: Get started with Play Console (registration fee)

**Reference.** Google, "Get started with Play Console," Play Console Help. [Online]. Available: https://support.google.com/googleplay/android-developer/answer/6112435. Accessed: Oct. 11, 2026.

**Summary.** The page walks through creating a Google Play developer account. One step is paying a one-time US$25 registration fee by credit or debit card. It also describes identity verification, which may ask for a government ID and a credit card, both in the developer's legal name. Personal accounts created after 13 November 2023 must meet extra testing requirements before publishing, and since early 2024 new personal-account developers must also verify that they have access to an Android device.

**Strengths and limitations.** It is the official source for the fee and the onboarding steps. The fee is small, but the identity, device and testing requirements add work and time that the fee does not show.

**Relevance to Mirsad.** A Play listing would cost $25 = **93.75 SAR**. The SPAP budgeted 100 SAR for it. The PWA approach makes this line 0 SAR.

### [23] Google: testing requirements for new personal developer accounts

**Reference.** Google, "App testing requirements for new personal developer accounts," Play Console Help. [Online]. Available: https://support.google.com/googleplay/android-developer/answer/14151465. Accessed: Oct. 11, 2026.

**Summary.** For personal accounts created after 13 November 2023, an app can only be published after a closed test. At least 12 testers must have been opted in to that test continuously for at least 14 days. After that the developer applies for production access from the Play Console dashboard. Testers who leave and rejoin do not count unless their 14 days are consecutive.

**Strengths and limitations.** It is official and specific. It adds at least two weeks to the schedule and requires recruiting testers, a cost in time that no budget line shows.

**Relevance to Mirsad.** It is a strong schedule argument for the PWA. A five-person team would need outside testers and a 14-day wait before any store release. A PWA can be installed from the browser on the day it is deployed.

### [24] Apple: Apple Developer Program membership

**Reference.** Apple Inc., "Become a member - Apple Developer Program," Apple Developer. [Online]. Available: https://developer.apple.com/programs/enroll/. Accessed: Oct. 11, 2026.

**Summary.** Apple's enrolment page sets membership at 99 USD per membership year, with local-currency prices shown during enrolment. Individuals need an Apple Account with two-factor authentication, must be of legal age, and must enrol under their legal name, which then appears as the App Store seller. Eligible non-profit organisations, accredited educational institutions and government entities can request a fee waiver; the page offers no waiver route for individual developers.

**Strengths and limitations.** It is the authoritative fee statement. The SAR local price may differ from the 99 USD peg conversion.

**Relevance to Mirsad.** A native iOS approval app would cost about 371.25 SAR **every year**, a cost the SPAP never budgeted. The PWA avoids it.

### [25] Eidson and Simmons (2023): Web Push for web apps on iOS and iPadOS

**Reference.** B. Eidson and J. Simmons, "Web Push for Web Apps on iOS and iPadOS," WebKit Blog, Feb. 16, 2023. [Online]. Available: https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/. Accessed: Oct. 11, 2026.

**Summary.** The WebKit team announced that iOS and iPadOS 16.4 add Web Push for web apps that the user has added to the Home Screen. It uses the standard Push API, Notifications API and Service Workers. Permission can only be requested in response to a user action, such as tapping a button. The post states that developers do not need Apple Developer Program membership to use it, and it advises servers to allow Apple's push endpoints.

**Strengths and limitations.** It is the primary source from the browser engine team. Push on iOS only works for installed Home Screen apps, so users must be shown how to install the PWA.

**Relevance to Mirsad.** This is the technical basis for dropping native apps. Approval requests can reach both iPhone and Android approvers through standard Web Push, with no store fees.

---

## F. Free resources and the zero-cost fallback

### [26] GitHub: Student Developer Pack

**Reference.** GitHub, "GitHub Student Developer Pack," GitHub Education. [Online]. Available: https://education.github.com/pack. Accessed: Oct. 11, 2026.

**Summary.** The pack bundles free offers for verified students. Items relevant to this budget:
- **Domains:** one year of a .me domain plus one SSL certificate for a year from Namecheap; a free domain on selected extensions (such as .dev, .app, .live) from Name.com; and one .TECH domain free for a year.
- **Cloud:** Microsoft Azure free services plus $100 credit for students aged 18 and over; Heroku credit of $13 per month for 24 months; a LocalStack licence.
- **Developer tools:** GitHub Codespaces at Pro level, GitHub Pro, GitHub Copilot Student, Doppler Team for secrets management, and Sentry for error monitoring.

DigitalOcean is no longer listed in the pack.

**Strengths and limitations.** The offers are substantial and free for every team member. Each offer has its own terms and some last only one year. Offers change without notice, and the pack page itself gives no eligibility rules (see [27]).

**Relevance to Mirsad.** It provides a free domain for the project year and $100 of Azure credit per eligible member, which could pay for part of the gateway hosting (Azure VM prices were not checked in this pass). Doppler Team helps keep API keys out of the repository, which matters for a security project. The disappearance of the DigitalOcean credit means a DigitalOcean VM must be paid in cash.

### [27] GitHub Docs: applying to GitHub Education as a student

**Reference.** GitHub, "Apply to GitHub Education as a student," GitHub Docs. [Online]. Available: https://docs.github.com/en/education/about-github-education/github-education-for-students/apply-to-github-education-as-a-student. Accessed: Oct. 11, 2026.

**Summary.** To qualify, a student must be at least 13, enrolled in a degree- or diploma-granting programme, own a personal GitHub account, and upload proof of current enrolment such as a dated student ID, schedule, transcript or enrolment letter. If the application asks for a school-issued email address, it must be added to the GitHub account and verified before applying.

**Strengths and limitations.** It is the official eligibility rule. It does not say how long the benefits last before the student must verify again.

**Relevance to Mirsad.** All five team members are enrolled at PSU, so each can apply and claim individual benefits (for example, up to five separate $100 Azure credits for members aged 18 or older). Applying early in the semester avoids delays from verification.

### [28] Cloudflare: Cloudflare Tunnel

**Reference.** Cloudflare, "Cloudflare Tunnel" and "Get started," Cloudflare Docs. [Online]. Available: https://developers.cloudflare.com/tunnel/ and https://developers.cloudflare.com/tunnel/get-started/. Accessed: Oct. 11, 2026.

**Summary.** Cloudflare Tunnel connects a service on a private machine to Cloudflare's network through an outbound-only connector (`cloudflared`). The service can then be published under a public hostname without opening inbound ports. The overview page states that the product is available on all plans. Published hostnames are mapped to local services, for example `app.example.com` pointing to `http://localhost:8080`. The "Get started" page lists a domain on Cloudflare as a prerequisite for publishing applications.

**Strengths and limitations.** No VM or public IP is needed, and traffic reaches the service through Cloudflare's network. Publishing an application needs a domain added to Cloudflare. All traffic also passes through a third party.

**Relevance to Mirsad.** In the fallback plan, a lab machine or team laptop runs the gateway and the PWA backend, and a named tunnel on a free domain from [26] exposes it over HTTPS at no cost.

### [29] Cloudflare: Quick Tunnels (TryCloudflare)

**Reference.** Cloudflare, "Quick Tunnels," Cloudflare Docs. [Online]. Available: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/. Accessed: Oct. 11, 2026.

**Summary.** Quick Tunnels give a local service a temporary `trycloudflare.com` hostname without a Cloudflare account or domain. The hostname changes every time a tunnel is created, and the URL stops working when the `cloudflared` process stops. They are meant for testing and development and come with no uptime guarantee. Each tunnel accepts up to 200 in-flight requests, and Server-Sent Events (SSE) are not supported.

**Strengths and limitations.** This is the quickest zero-cost way to put a laptop-hosted demo on the internet. The hostname changes each time, which breaks installed PWAs and push subscriptions, and the lack of SSE support can break streaming transports.

**Relevance to Mirsad.** It is a last-resort fallback for a single live demo. If Mirsad's MCP or approval channel uses SSE, Quick Tunnels cannot be used for it, so a named tunnel [28] or a free VM [30] is the better fallback.

### [30] Oracle Cloud Infrastructure: Always Free resources

**Reference.** Oracle, "Always Free Resources," Oracle Cloud Infrastructure Documentation. [Online]. Available: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm. Accessed: Oct. 11, 2026.

**Summary.** Every OCI tenancy gets 1,500 OCPU-hours and 9,000 GB-hours per month of Arm-based Ampere A1 compute free, which the page says is equivalent to 2 OCPUs and 12 GB of memory. It can be used as one instance or split into two. Tenancies also get up to two small AMD micro instances with 1 GB each. Always Free instances must be created in the home region. Oracle may reclaim idle instances: an instance counts as idle if, over a 7-day period, 95th-percentile CPU utilisation, network utilisation and (for A1 shapes only) memory utilisation are all below 20%.

**Strengths and limitations.** The free A1 allowance exceeds the 2 vCPU / 4 GB requirement at no cost. A demo gateway that sits idle may be reclaimed, capacity errors are possible, and sign-up has its own verification steps.

**Relevance to Mirsad.** It is a zero-cost VM option for the fallback plan. The team must keep the gateway lightly busy (for example, scheduled health checks and benchmark traffic) and keep its deployment scripted so a reclaimed instance can be rebuilt quickly.

### [31] Google: Gemini Developer API pricing (free tier)

**Reference.** Google, "Gemini Developer API pricing," Google AI for Developers. [Online]. Available: https://ai.google.dev/gemini-api/docs/pricing. Accessed: Oct. 11, 2026.

**Summary.** The page lists a Free tier and a Paid tier for each Gemini model. For Gemini 3.8 Flash, input and output (including thinking tokens) are free of charge on the Free tier. The Paid tier costs $0.75 input and $3.75 output per 1M tokens through 31 December 2026, doubling to $1.50 and $7.50 from 1 January 2027. The page marks Free-tier content as used to improve Google's products, while paid-tier content is not.

**Strengths and limitations.** It gives a no-cost cloud model for a comparison run. Free-tier prompts may be used by Google, rate limits apply, and the paid price doubles in the middle of the project year.

**Relevance to Mirsad.** In the zero-cost plan, one cloud-model comparison can run on the Gemini free tier, but only on synthetic benchmark data with no personal or confidential content. The scheduled 2027 price rise is another example of the price volatility that the contingency line covers.

---

## G. Cost calculations

### G.1 LLM API: ~2,000 episodes × ~6,000 tokens (12M tokens per model per full run)

| Scenario (per full 2,000-episode run) | Claude Sonnet 5.5 [2] | OpenAI gpt-6.1-sol [5] |
|---|---|---|
| List price per 1M tokens (input / output) | $2 / $10 | $2 / $10 |
| Base case: 5k in + 1k out per episode (10M in, 2M out) | $40 = **150 SAR** | $40 = **150 SAR** |
| Same, through the Batch API (50% off) | $20 = 75 SAR | $20 = 75 SAR |
| Output-heavier: 4k in + 2k out (8M in, 4M out) | $56 = 210 SAR | $56 = 210 SAR |
| Base case + 30% newer-tokenizer allowance [2] | $52 = 195 SAR | n/a |
| Bounds (all 12M input / all 12M output) | $24–$120 = 90–450 SAR | $24–$120 = 90–450 SAR |

One base-case run on both providers costs $80 = **300 SAR**, and the output-heavier case on both costs $112 = 420 SAR. Batch pricing applies only when episodes can be submitted asynchronously. Multi-turn agent episodes need each turn's result before the next turn, so the budget assumes Standard pricing and treats Batch as a possible saving.

### G.2 Cloud VM: 2 vCPU / 4 GB for 6 months

| Provider and plan | Price as shown | Monthly (USD) | Monthly (SAR) | 6 months (SAR) | Orderable on 11 Oct 2026? |
|---|---|---|---|---|---|
| Hetzner CX23 (2 vCPU, 4 GB, 40 GB) + IPv4 [9], [10] | €5.49 / $6.49 excl. IPv4; IPv4 €0.50 / $0.60 | $7.09 | 26.59 | **159.53** | No, labelled "not available" [11] |
| Hetzner CPX22 (2 vCPU AMD, 4 GB, 80 GB) + IPv4 [9], [10] | €19.49 / $22.99 excl. IPv4 | $23.59 | 88.46 | **530.78** | Not labelled unavailable [11] |
| DigitalOcean Basic 4 GiB / 2 vCPU / 80 GiB [12] | $24.00/mo | $24.00 | 90.00 | **540.00** | Yes (no restriction shown on the page) |
| AWS Lightsail 4 GB / 2 vCPU / 80 GB, IPv4 [13] | $24 USD/mo | $24.00 | 90.00 | **540.00** | Yes (no restriction shown on the page) |
| AWS Lightsail same bundle, IPv6-only [13] | $20 USD/mo | $20.00 | 75.00 | 450.00 | Yes (no restriction shown), but not suitable for a public demo |

### G.3 Domain, TLS, and app stores

| Item | Price as shown | SAR |
|---|---|---|
| .com at Porkbun, 1 year (registration = renewal) [14] | $11.08 | 41.55 |
| .sa at Sahara Net (licensed registrar [16]), year 1 / renewal [17] | SAR 52.18 / SAR 86.09 | 52.18 / 86.09 |
| .com at Sahara Net [17] | SAR 75.00 | 75.00 |
| TLS certificate, Let's Encrypt [18] | free | 0 |
| Google Play developer registration, one-time [22] | US$25 | 93.75 |
| Apple Developer Program, per year [24] | 99 USD | 371.25 (local price may differ) |

---

## H. Budget table: original SPAP vs. revised (SAR)

| Line | Original SPAP | Revised | Justification (with sources) |
|---|---:|---:|---|
| LLM API usage | 750 | **450** | Development and most of the evaluation run on local Ollama models at no cost [7], through the same OpenAI-compatible tool-calling interface [8]. Paid APIs are kept for one confirmatory 2,000-episode run on each mid-tier model: Claude Sonnet 5.5 at $2/$10 per MTok [2], [3] and gpt-6.1-sol at $2/$10 per MTok [5], [6]. The base case for both is 300 SAR (G.1). The 450 SAR ($120) line also covers the output-heavier case (420 SAR), which accounts for reasoning tokens billed as output [5] and Claude's larger token counts [2]. Credits are non-refundable and expire after a year [4], so they are bought right before the run. |
| Cloud VM (2 vCPU / 4 GB, 6 months) | 600 | **540** | The VM now runs only the gateway, the PWA backend and the audit log, not a model, so 2 vCPU / 4 GB is enough. Two orderable providers both cost $24/month: DigitalOcean [12] and AWS Lightsail [13], so 6 × 90 = 540 SAR. Hetzner CPX22 is similar at 530.78 SAR [9], [10]. Hetzner CX23 would cost 159.53 SAR but cannot currently be ordered [11]; if it becomes available, the saving goes back to contingency. |
| Google Play registration | 100 | **0** | The approval client is a PWA. Web Push works on Android and on iOS 16.4+ Home Screen apps without store accounts [25]. This avoids the US$25 fee (93.75 SAR) [22] and the 12-tester, 14-day closed-test requirement [23]. It also avoids Apple's 99 USD per year (about 371 SAR) [24], which the SPAP never budgeted. |
| Domain + TLS | 60 | **45** | A .com at Porkbun costs $11.08 = 41.55 SAR including ICANN fees [14], rounded up to 45 SAR. TLS from Let's Encrypt is free [18] and is required because service workers need HTTPS [21]. Optional: a .sa name at 52.18 SAR in the first year [15], [17] if a member with Saudi nationality registers it. Free alternatives are in Section I [26]. |
| Contingency | 150 | **150** | About 14.5% of the 1,035 SAR subtotal. It covers price changes, which are documented during 2026: Hetzner's June 2026 increases of 1.38× for CX23 and 2.44× for CPX22 [9] and the scheduled January 2027 doubling of Gemini paid prices [31]. It also covers any VAT or card and foreign-exchange fees, which the vendor prices either exclude explicitly (Hetzner [9], [10]) or do not mention, and extra API reruns if the benchmark is repeated. |
| **Total** | **1,660** | **1,185** | **Saving 475 SAR (28.6%).** |

**Notes on the revised budget.**
1. All USD conversions use the official 3.75 SAR/USD peg [1].
2. No line depends on a student credit. Student benefits [26] and the Batch API discount (up to 150 SAR on the LLM line [2], [5]) are extra savings that would go back to contingency.
3. If the department or a sponsor can fund only part of the budget, the lines should be cut in this order: (a) the VM, by moving to the Azure student credit or the Oracle free tier; (b) the domain, by using a pack domain; (c) the LLM line, by running the confirmatory cloud run on 1,000 episodes instead of 2,000 (about 225 SAR).

---

## I. Zero-cost fallback plan (0 SAR)

If no money is approved, Mirsad can still be built, evaluated and demonstrated:

| Need | Zero-cost substitute | Caveats |
|---|---|---|
| LLM for development and the full benchmark | Ollama with open-weight models on team laptops or PSU lab machines (MIT licence, no usage fee) [7], via its OpenAI-compatible tool-calling API [8] | Weaker models than the cloud mid-tier ones; slower runs. Results must be labelled "local models". |
| Cloud-model comparison | Gemini 3.8 Flash Free tier [31] on synthetic benchmark data only | Free-tier content may be used by Google; rate limits; a different vendor from the two in the paid plan. Otherwise, report that the cloud comparison was not run. |
| Public gateway host | (a) Azure for Students $100 credit through the GitHub Student Developer Pack [26], [27]; (b) OCI Always Free Ampere A1, 2 OCPU / 12 GB [30]; (c) a lab machine behind a free Cloudflare Tunnel [28] | (b) idle instances can be reclaimed, so keep light traffic running and script the rebuild; (c) depends on the machine staying on. |
| Domain | Free .me (Namecheap, one year), a Name.com domain, or a .TECH domain through the pack [26]; or no domain at all, using a Let's Encrypt IP-address certificate [20] | The Namecheap .me and .TECH offers are free for one year, which is enough for the project year; the pack page states no term for the Name.com offer. A named Cloudflare Tunnel needs the domain added to Cloudflare [28]. IP-address certificates last 160 hours (just over 6 days) and need automated renewal. |
| TLS | Let's Encrypt [18] (or Cloudflare's edge certificate when tunnelling [28]) | Renewal must follow the changing lifetimes [19], [20]. |
| Mobile approvals | PWA with standard Web Push; no Google Play or Apple fees [21], [25] | iOS users must add the app to the Home Screen first. |
| One-off live demo | Quick Tunnel `trycloudflare.com` URL [29] | Testing only; the URL changes on every start; no SSE; 200 in-flight request cap. Use only if the alternatives above are unavailable. |

---

## Synthesis

**Themes.**
1. **The design decisions change costs more than any price change does.** Local inference [7], [8] cuts the variable LLM cost to one confirmatory run. The PWA approach [25] removes the store line completely and avoids an Apple fee the SPAP had not counted [24]. Together they account for 400 of the 475 SAR saved.
2. **Mid-tier frontier API prices have converged.** Claude Sonnet 5.5 and gpt-6.1-sol both list at $2 input / $10 output per MTok, with matching 50% batch discounts [2], [5]. The cost of a run now depends mostly on how many tokens each model produces (reasoning tokens [5], tokenizer differences [2]), not on its list price.
3. **The small-VM market price is about $24 per month, and the cheap tier is volatile.** Three providers agree on $24 per month for 2 vCPU / 4 GB [12], [13] or close to it [9]. Hetzner's much cheaper plan was repriced in June 2026 and cannot currently be ordered [9], [11]. Budget estimates should use a price that can actually be ordered, not the lowest list price.
4. **Security infrastructure is free but needs maintenance.** TLS costs nothing [18], but certificate lifetimes are shrinking during the project year [19], [20]. HTTPS is a hard requirement for the approval PWA [21]. The real cost is automation and monitoring, not money.
5. **"Free" options come with their own costs**, such as data use (Gemini free tier [31]), idle reclamation (OCI [30]), one-year terms (most pack domains [26]), or missing transport features (Quick Tunnels [29]). The fallback plan states each one so that the team does not inherit hidden constraints.

**Gaps this budget work addresses for Mirsad.**
- The SPAP gave single figures without sources. Every revised line is now tied to a dated official page, which an examiner can check.
- The SPAP budgeted Google Play but not Apple. The revised plan removes both store costs and explains why, citing the WebKit Web Push announcement [25].
- The SPAP gave no token model for "LLM API usage". The revised line is derived from an explicit episode count, input/output split and sensitivity range (G.1), so changes in benchmark size can be re-costed in minutes.
- Billing rules (non-refundable, expiring API credits [4]) and policy rules (.sa eligibility [15]) that affect when and how money is spent are now documented.

**Remaining uncertainties.**
- Whether foreign vendors charge Saudi VAT on these purchases was not confirmed against an official ZATCA page in this research pass, so taxes are left to contingency.
- OpenAI's prepaid-credit minimum and expiry could not be checked because the help page blocked automated access. They should be confirmed in the billing console before buying.
- The real token count per episode should be measured on the first 50 local episodes, and the LLM line (G.1 and Section H) re-costed before any paid credits are bought.

---

## References

[1] Saudi Central Bank (SAMA), "SAMA Affirms Commitment to Exchange Rate Policy," SAMA Media Center, 2020. [Online]. Available: https://www.sama.gov.sa/en-US/MediaCenter/News/Pages/news-557.aspx. Accessed: Oct. 11, 2026.

[2] Anthropic, "Pricing," Claude Platform Docs. [Online]. Available: https://platform.claude.com/docs/en/about-claude/pricing. Accessed: Oct. 11, 2026.

[3] Anthropic, "Models overview," Claude Platform Docs. [Online]. Available: https://platform.claude.com/docs/en/models/overview. Accessed: Oct. 11, 2026.

[4] Anthropic, "How do I pay for my Claude API usage?," Claude Help Center. [Online]. Available: https://support.claude.com/en/articles/8977456. Accessed: Oct. 11, 2026.

[5] OpenAI, "Pricing," OpenAI API Docs. [Online]. Available: https://developers.openai.com/api/docs/pricing. Accessed: Oct. 11, 2026.

[6] OpenAI, "Models," OpenAI API Docs. [Online]. Available: https://developers.openai.com/api/docs/models. Accessed: Oct. 11, 2026.

[7] Ollama, "ollama/ollama," GitHub repository, MIT License. [Online]. Available: https://github.com/ollama/ollama. Accessed: Oct. 11, 2026.

[8] Ollama, "OpenAI compatibility," Ollama Docs. [Online]. Available: https://docs.ollama.com/api/openai-compatibility. Accessed: Oct. 11, 2026.

[9] Hetzner Online GmbH, "Hetzner Price Adjustment 15 June 2026," Hetzner Docs, ID GE-D9256, Jun. 15, 2026. [Online]. Available: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/. Accessed: Oct. 11, 2026.

[10] Hetzner Online GmbH, "IP pricing," Hetzner Docs. [Online]. Available: https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/. Accessed: Oct. 11, 2026.

[11] Hetzner Online GmbH, "Cheap cloud-hosting – low vps prices for developers" and "Hetzner Virtual Private Server: Best Price-Performance Ratio." [Online]. Available: https://www.hetzner.com/cloud/cost-optimized/ and https://www.hetzner.com/cloud/regular-performance/. Accessed: Oct. 11, 2026.

[12] DigitalOcean, "Droplet Pricing." [Online]. Available: https://www.digitalocean.com/pricing/droplets. Accessed: Oct. 11, 2026.

[13] Amazon Web Services, "Amazon Lightsail Pricing." [Online]. Available: https://aws.amazon.com/lightsail/pricing/. Accessed: Oct. 11, 2026.

[14] Porkbun, "Domain Name Pricing." [Online]. Available: https://porkbun.com/products/domains. Accessed: Oct. 11, 2026.

[15] Communications, Space & Technology Commission (SaudiNIC), "Saudi Domain Names Registration Regulations," ver. 5.0, Feb. 2024. [Online]. Available: https://nic.sa/en/help/regulation. Accessed: Oct. 11, 2026.

[16] SaudiNIC, "Registrars." [Online]. Available: https://nic.sa/en/registrars. Accessed: Oct. 11, 2026.

[17] Sahara Net, "Domain Pricing." [Online]. Available: https://shop.sahara.com/index.php?rp=/domain/pricing. Accessed: Oct. 11, 2026.

[18] Internet Security Research Group, "About Let's Encrypt" and "FAQ," Let's Encrypt. [Online]. Available: https://letsencrypt.org/about/ and https://letsencrypt.org/docs/faq/. Accessed: Oct. 11, 2026.

[19] M. McPherrin, "Decreasing Certificate Lifetimes to 45 Days," Let's Encrypt, Dec. 2, 2025. [Online]. Available: https://letsencrypt.org/2025/12/02/from-90-to-45. Accessed: Oct. 11, 2026.

[20] M. McPherrin, "6-day and IP Address Certificates are Generally Available," Let's Encrypt, Jan. 15, 2026. [Online]. Available: https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability. Accessed: Oct. 11, 2026.

[21] MDN contributors, "Service Worker API," MDN Web Docs, Mozilla. [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API. Accessed: Oct. 11, 2026.

[22] Google, "Get started with Play Console," Play Console Help. [Online]. Available: https://support.google.com/googleplay/android-developer/answer/6112435. Accessed: Oct. 11, 2026.

[23] Google, "App testing requirements for new personal developer accounts," Play Console Help. [Online]. Available: https://support.google.com/googleplay/android-developer/answer/14151465. Accessed: Oct. 11, 2026.

[24] Apple Inc., "Become a member - Apple Developer Program," Apple Developer. [Online]. Available: https://developer.apple.com/programs/enroll/. Accessed: Oct. 11, 2026.

[25] B. Eidson and J. Simmons, "Web Push for Web Apps on iOS and iPadOS," WebKit Blog, Feb. 16, 2023. [Online]. Available: https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/. Accessed: Oct. 11, 2026.

[26] GitHub, "GitHub Student Developer Pack," GitHub Education. [Online]. Available: https://education.github.com/pack. Accessed: Oct. 11, 2026.

[27] GitHub, "Apply to GitHub Education as a student," GitHub Docs. [Online]. Available: https://docs.github.com/en/education/about-github-education/github-education-for-students/apply-to-github-education-as-a-student. Accessed: Oct. 11, 2026.

[28] Cloudflare, "Cloudflare Tunnel" and "Get started," Cloudflare Docs. [Online]. Available: https://developers.cloudflare.com/tunnel/ and https://developers.cloudflare.com/tunnel/get-started/. Accessed: Oct. 11, 2026.

[29] Cloudflare, "Quick Tunnels," Cloudflare Docs. [Online]. Available: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/. Accessed: Oct. 11, 2026.

[30] Oracle, "Always Free Resources," Oracle Cloud Infrastructure Documentation. [Online]. Available: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm. Accessed: Oct. 11, 2026.

[31] Google, "Gemini Developer API pricing," Google AI for Developers. [Online]. Available: https://ai.google.dev/gemini-api/docs/pricing. Accessed: Oct. 11, 2026.

---

## Verification log

*Independent fact-check carried out on 11 October 2026. Every reference was re-opened on its original or official page, through a page fetch, a raw-HTML download searched for the exact figure, or the GitHub REST API for [7]. All arithmetic in Sections B to H was recomputed and found correct: 150 / 75 / 210 / 195 SAR per provider; 300 and 420 SAR for both providers; 159.53, 530.78, 540 and 450 SAR for the VMs; 41.55, 93.75 and 371.25 SAR; a 1,035 SAR subtotal; contingency of 14.5%; a 1,185 SAR total; and a saving of 475 SAR (28.6%).*

**Confirmed without change.**
- [1] SAMA: title, the 3.75 SAR/USD peg, the stability and reserves wording, and the date shown as "5/4/2020".
- [2] Anthropic pricing: Sonnet 5.5 at $2 input, $2.50 / $4 cache writes, $0.10 cache hits and $10 output; Batch $1 / $5; the roughly 30% newer-tokenizer note (Claude 4.7 and later, compared with Sonnet 4.6 and earlier); 286 tool-use system-prompt tokens (auto/none).
- [3] Models overview: the line-up Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5; Sonnet 5.5's description, ID `claude-sonnet-5-5`, 1M context window, 128K maximum output and $2 / $10 price; the statement that all models support tool use; and retirement no sooner than 28 Sep 2027, with Bedrock and Google Cloud setting their own dates.
- [4] Claude Help Center: Admin or Billing role required, credits usable immediately, optional auto-reload, one-year expiry that cannot be extended, purchases non-refundable, and no minimum purchase stated.
- [5] OpenAI pricing: the Standard, Batch, Flex, Fast and Ultrafast tiers; the ≤272K short-context threshold; gpt-6.1-sol at $2.00 / $0.10 / $2.50 / $10.00 (Standard) and $1.00 / $0.05 / $1.25 / $5.00 (Batch); and the Output tooltip on reasoning tokens, found in the raw HTML.
- [6] OpenAI models: the Astra, 6.1 Sol and Luna descriptions; Sol's tools listed as Functions, Web search, File search and Computer use; and effort levels low to max.
- [7] Ollama: MIT licence and REST API (README), and latest release v0.40.3 published 11 Oct 2026 (GitHub API).
- [8] Ollama OpenAI compatibility: "subset of the OpenAI API", with Tools supported on `/v1/chat/completions` and `/v1/responses`.
- [9] Hetzner price notice: ID GE-D9256, created 15 Jun 2026 and last changed 8 Jul 2026; prices apply to new orders and rescales and exclude IPv4 and VAT; CX23 €3.99→€5.49 ($4.99→$6.49) and CPX22 €7.99→€19.49 ($9.49→$22.99); EUR increases of 1.30× to 1.38× for CX/CAX and 2.44× to 2.75× for CPX.
- [10] Hetzner IP pricing: primary IPv4 €0.50 ($0.60) per month excluding VAT, IPv6 free, last changed 13 Apr 2023.
- [12] DigitalOcean: 4 GiB / 2 vCPU / 80 GiB / 4,000 GiB at $0.03571/h or $24.00/mo; per-second billing from 1 Jan 2026 with a 60 s or $0.01 minimum; monthly cap; public IPv4 included in bundled plans.
- [13] Lightsail: $24 for the 4 GB / 2 vCPU / 80 GB / 4 TB bundle with public IPv4, $20 IPv6-only, and a Free Tier mention with no bundle detail.
- [14] Porkbun: .com $11.08 to register, renew or transfer; "All prices include ICANN and any other fees"; ICANN-accredited.
- [17] Sahara Net: .sa and its subzones at SAR 52.18 new, SAR 52.18 transfer and SAR 86.09 renewal; .com SAR 75.00; no VAT statement.
- [20] Let's Encrypt (McPherrin, 15 Jan 2026): 160-hour certificates, IPv4 and IPv6 support, the `shortlived` profile, and IP certificates issued only as short-lived certificates.
- [21] MDN: proxy description, offline, push and background sync, and the secure-context requirement with `http://localhost` treated as secure.
- [25] WebKit (Eidson and Simmons, 16 Feb 2023): iOS/iPadOS 16.4, Home Screen requirement, Push, Notifications and Service Worker APIs, permission only on user interaction, no Developer Program membership needed, and the advice to allow `*.push.apple.com`.
- [26] GitHub Student Developer Pack: Namecheap .me (one year) and SSL certificate, Name.com, .TECH (one year), Azure $100 credit (aged 18+), Heroku $13/month for 24 months, LocalStack, Codespaces Pro, GitHub Pro, Copilot Student, Doppler Team and Sentry; DigitalOcean absent.
- [30] Oracle Always Free: 1,500 OCPU-hours and 9,000 GB-hours of A1 compute (2 OCPU / 12 GB), up to two E2.1.Micro instances with 1 GB each, home region only.
- [31] Gemini 3.8 Flash: free on the Free tier; paid $0.75 / $3.75 through 31 Dec 2026 and $1.50 / $7.50 from 1 Jan 2027; output includes thinking tokens; Free-tier content used to improve products, Paid-tier content not used.
- Page titles of all cited URLs matched the reference entries.

**Corrected.**
- [2]: "the page does not discuss taxes" was not accurate. The page mentions tax only for the AWS and Azure Marketplace billing routes. Reworded.
- [3]: the References list gave `/docs/en/about-claude/models/overview`, which returns a 307 redirect to `/docs/en/models/overview`. The list now uses the canonical URL, matching the entry.
- [5]: removed "promotional prices", which the page does not show. Replaced it with a change the page does record (Priority processing renamed Fast mode on 30 Jul 2026).
- [11]: the "product is currently unavailable" text is a generic tooltip attached to every Create button on both pages, so it is not a CX-specific notice. Also, "Price incl. IPv4" appears on both pages, not only on the Regular Performance page. Both points reworded. The "not available" label on all eight CX/CAX plans, and its absence on CPX22, were confirmed in the HTML.
- [15]: added the version and date shown on the page (ver. 5.0, Feb. 2024). Eligibility, .sa/.com.sa/.edu.sa/.med.sa/pub.sa rules and the absence of a price list were confirmed.
- [16]: removed "(by stc)". The page lists the registrar only as "Solutions", with an Arabic company name and no stc branding. The registrar list and the home-page rule that non-government registrations go only through licensed registrars were confirmed.
- [18]: "domain validation only and no paid support" was not on the About page. It is now sourced to the Let's Encrypt FAQ (DV only, no plans for OV/EV, no direct subscriber support), and the FAQ URL was added to the reference. "Browser-trusted" became "trusted" and "publicly logged" became "publicly recorded", following the page's wording.
- [19]: "began issuing 45-day certificates on 13 May 2026" was a past-tense claim that the Dec. 2025 post cannot support. Changed to "was scheduled to start". Added the profile names, the 10-day and 7-hour authorization-reuse periods, and the post's warning against a hard-coded 60-day renewal.
- [22]: the page ties device verification to new personal accounts "starting in early 2024", not to the 13 Nov 2023 cut-off, which applies to the testing requirement. Reworded.
- [23]: "for the preceding 14 days" changed to the page's "for at least 14 days".
- [24]: "not for individual students" was an inference. Now states what the page says: waivers for eligible non-profits, accredited educational institutions and government entities, and no route for individual developers.
- [26]: "enough to host a small gateway for several months" was unsupported, since Azure VM prices were not checked, so it was softened. In Section I, "pack domains are free for one year only" was corrected, because the Name.com offer states no term.
- [27]: the academic-email condition was reworded to match the page ("if the application asks for" a school email).
- [28]: replaced the unsourced "in practice a named tunnel needs a domain managed in Cloudflare" with the official prerequisite from the Tunnel "Get started" page ("A domain on Cloudflare (required to publish applications)"), and added that URL. Also removed "Cloudflare terminates TLS", which the cited pages do not state.
- [29]: the cited URL returns a 301 redirect to `/tunnel/get-started/quick-tunnels/`, so the reference was updated. Content confirmed: no account or domain needed; for testing and development; no uptime guarantee; 200 in-flight requests; no SSE; hostname changes each time; URL stops working when `cloudflared` stops.
- [30]: added the page's 95th-percentile qualifier for CPU, and that the memory threshold applies to A1 shapes only.
- Section G.2: "Orderable: Yes" for DigitalOcean and Lightsail is now "Yes (no restriction shown on the page)", because neither page states availability explicitly.
- Section H (contingency): "Hetzner's June 2026 increases of 1.4× to 2.4×" did not match the table, where increases range from 1.30× to 2.75×. It now gives the two plans actually used, 1.38× (CX23) and 2.44× (CPX22). "Which none of the vendor prices include" (VAT and fees) was an overclaim and now reads "exclude explicitly (Hetzner) or do not mention".

**Not independently verifiable (left as stated, as project context or research-process notes).** These are the SPAP's original budget lines, the team size and enrolment at PSU, the statement that Ollama's cloud pricing page could not be reached, and the statement that OpenAI's help page blocked automated access.

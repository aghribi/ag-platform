import type { Metadata } from "next";
import Link from "next/link";
import { CONTACT_EMAIL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Terms and privacy · ag-tools",
  description:
    "Terms of use and privacy notice for the ag-tools hosted API: PII Vault, EvalForge, Guardrail and DocParse.",
};

const sections: { title: string; items?: string[]; body?: string }[] = [
  {
    title: "1. Service description",
    body: "ag-tools is a hosted API and dashboard for the open-source libraries ag-pii-vault (PII detection and tokenization), ag-evalforge (LLM output evaluation), ag-guardrail (content safety policies and audit logging) and ag-docparse (structured document extraction). It is a free service operated by an individual. It supports your compliance work but is not legal advice, and using it does not by itself make your systems compliant with any regulation.",
  },
  {
    title: "2. Accounts and API keys",
    items: [
      "You must be at least 18 years old to create an account.",
      "You are responsible for keeping your account credentials and API keys confidential. Requests authenticated with your keys are treated as yours.",
      "Rotate or revoke a key immediately from the dashboard if you suspect it has been exposed.",
      "One account per user. Team usage is supported through organisations with seat invitations, not credential sharing.",
    ],
  },
  {
    title: "3. Limits and fair use",
    items: [
      "Each account has monthly usage limits per product, shown in the dashboard. Limits reset at the start of each calendar month.",
      "Higher limits can be requested by email and are granted at the operator's discretion.",
      "When a limit is reached, the API returns an explicit quota-exceeded error.",
      "Rate limits may apply to protect the service. Attempts to circumvent limits or rate limits are a breach of these terms.",
    ],
  },
  {
    title: "4. Acceptable use",
    items: [
      "Do not use the API to process data you have no legal right to process.",
      "Do not use the service for any unlawful purpose or in violation of applicable regulations, including EU data protection law.",
      "Do not attempt to circumvent authentication, limits or rate limits.",
    ],
  },
  {
    title: "5. Your data",
    items: [
      "You retain full ownership of all content you send to the API and of the outputs generated for you.",
      "PII Vault token mappings are stored encrypted and are only accessible with your API keys. You can clear your vault at any time from the account page.",
      "API payloads are not used to train models.",
      "Usage metadata (volumes, timestamps, product, status) is retained for quota accounting and audit features.",
      "You can export your usage data and delete your account (including vault data and API keys) from the dashboard at any time.",
    ],
  },
  {
    title: "6. Privacy",
    items: [
      "Data controller: Adnan Ghribi. Contact: " + CONTACT_EMAIL + ".",
      "Data processed: account email and password hash, API keys (stored hashed), usage metadata, and the content you submit to the API for the duration needed to serve each request, plus the vault entries and audit logs you choose to store.",
      "Purpose and legal basis: providing the service you signed up for (performance of a contract).",
      "Some requests are processed by third-party providers (OpenAI, Anthropic, or LlamaParse for document OCR) when a product feature needs them. Transactional email is sent through Resend.",
      "Data is kept until you delete it or delete your account.",
      "You can access, export, correct or delete your data from the dashboard, or by writing to the contact address. You can also lodge a complaint with the CNIL (www.cnil.fr).",
    ],
  },
  {
    title: "7. EU AI Act positioning",
    body: "The products map to specific controls of Regulation (EU) 2024/1689 (the EU AI Act) and expose machine-readable compliance metadata. This mapping is informational: responsibility for your own classification, obligations and conformity under the EU AI Act and any other regulation remains yours.",
  },
  {
    title: "8. Service availability and changes",
    items: [
      "The service is provided without an uptime guarantee.",
      "Features may be added, changed or retired. Significant changes are announced to registered users by email.",
    ],
  },
  {
    title: "9. Intellectual property",
    items: [
      "The libraries and this platform are open source. Each repository states its license.",
    ],
  },
  {
    title: "10. Disclaimer and limitation of liability",
    body: "The service is provided “as is” without warranty of any kind. AI-based detection, evaluation and extraction are probabilistic and may produce false positives or false negatives; you remain responsible for reviewing outputs used in production systems. To the fullest extent permitted by law, the operator is not liable for indirect damages arising out of the use of the service.",
  },
  {
    title: "11. Termination",
    body: "Accounts that violate these terms may be suspended or deleted. You may delete your account at any time from the dashboard; deletion removes your vault data and API keys.",
  },
  {
    title: "12. Governing law",
    body: "These terms are governed by French law, without prejudice to your rights as a consumer under your local jurisdiction.",
  },
];

export default function TermsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-16">
      <div className="mb-10 flex items-center gap-3">
        <svg width="36" height="36" viewBox="0 0 44 44" fill="none" aria-label="ag-tools">
          <rect width="44" height="44" rx="11" fill="#0c1a2e" />
          <circle cx="22" cy="22" r="13" stroke="#0ea5e9" strokeWidth="2.5" strokeDasharray="68 14" strokeLinecap="round" transform="rotate(-30 22 22)" />
          <circle cx="22" cy="22" r="5" fill="#0ea5e9" />
          <circle cx="32" cy="13" r="3" fill="#d946ef" />
        </svg>
        <div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">Terms and privacy</h1>
          <p className="text-sm text-ink-3">Last updated: October 2026</p>
        </div>
      </div>

      <div className="space-y-8 text-sm leading-relaxed text-ink-2">
        {sections.map((s) => (
          <section key={s.title}>
            <h2 className="text-base font-bold text-ink mb-2">{s.title}</h2>
            {s.body && <p>{s.body}</p>}
            {s.items && (
              <ul className="list-disc pl-5 space-y-1.5">
                {s.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}

        <section>
          <h2 className="text-base font-bold text-ink mb-2">13. Operator and contact</h2>
          <p>
            ag-tools is operated by Adnan Ghribi. Questions about these terms or your data:{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-sky-600 hover:underline">{CONTACT_EMAIL}</a>
          </p>
        </section>
      </div>

      <div className="mt-12 pt-6 border-t border-edge text-sm">
        <Link href="/" className="text-sky-600 hover:underline">&larr; Back to ag-tools</Link>
      </div>
    </main>
  );
}

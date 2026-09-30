import { useEffect, useState } from "react";

// Chrome-only i18n (nav, page titles, buttons — not evidence text, which the language guard already keeps
// factual and untranslated by design). Flagged in the blueprint as needing native-speaker review before it
// ships as the default; it is opt-in here via the header toggle, English remains the default.
export type Lang = "en" | "hi";
const KEY = "sutradhar.lang";

const DICT: Record<string, string> = {
  Requirements: "आवश्यकताएँ",
  Console: "कंसोल",
  Cases: "मामले",
  Govern: "शासन",
  Academy: "अकादमी",
  "Open demo": "डेमो खोलें",
  "Runs offline": "ऑफ़लाइन चलता है",
  "Synthetic data": "कृत्रिम डेटा",
  "Model registry": "मॉडल रजिस्ट्री",
  "Audit chain": "ऑडिट श्रृंखला",
  Settings: "सेटिंग्स",
  "Recent activity": "हाल की गतिविधि",
  "Leads, most urgent first": "लीड, सबसे अत्यावश्यक पहले",
  "Why this was flagged": "यह क्यों चिह्नित हुआ",
  "Against this reading": "इस निष्कर्ष के विरुद्ध",
  "What would clear this": "इसे क्या हल कर सकता है",
  "Add to case": "मामले में जोड़ें",
  "Investigate graph": "ग्राफ़ जाँचें",
  "New case title (3+ characters)": "नए मामले का शीर्षक (3+ अक्षर)",
  "Create case": "मामला बनाएँ",
  Notes: "टिप्पणियाँ",
  "Add note": "टिप्पणी जोड़ें",
  "Export evidence": "साक्ष्य निर्यात करें",
  Start: "शुरू करें",
  Submit: "जमा करें",
  Questions: "प्रश्न",
  "Scenario Studio": "परिदृश्य स्टूडियो",
  Result: "परिणाम",
};

export function useLang(): [Lang, (l: Lang) => void] {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      return (localStorage.getItem(KEY) as Lang) === "hi" ? "hi" : "en";
    } catch {
      return "en";
    }
  });
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* private mode */
    }
  };
  return [lang, setLang];
}

export function t(lang: Lang, s: string): string {
  if (lang === "en") return s;
  return DICT[s] ?? s;
}

import { useCallback, useState } from 'react'

export type Language = 'en' | 'tr'

const dictionary = {
  en: {
    'status.ready': 'Ready', 'status.planning': 'Replanning', 'status.clarification': 'Clarification needed',
    'status.abstained': 'Disruption unresolved', 'status.verified': 'Verified', 'status.no_agreement': 'No agreement',
    'status.infeasible': 'No feasible meeting', 'status.search_incomplete': 'Search incomplete',
    'status.model_error': 'Model error', 'status.system_error': 'Internal error', 'status.verification_failed': 'Verification failed',
    'incidents.title': 'Active disruptions', 'incidents.empty': 'No disruption is active.',
    'incidents.retract': 'Retract', 'retry': 'Retry this run', 'share': 'Copy link to this run', 'copied': 'Link copied',
    'language': 'Türkçe', 'theme': 'Switch theme', 'round': 'Clarification round',
  },
  tr: {
    'status.ready': 'Hazır', 'status.planning': 'Yeniden planlanıyor', 'status.clarification': 'Açıklama gerekiyor',
    'status.abstained': 'Aksama çözülemedi', 'status.verified': 'Doğrulandı', 'status.no_agreement': 'Uzlaşma yok',
    'status.infeasible': 'Uygun buluşma yok', 'status.search_incomplete': 'Arama tamamlanamadı',
    'status.model_error': 'Model hatası', 'status.system_error': 'İç hata', 'status.verification_failed': 'Doğrulama başarısız',
    'incidents.title': 'Etkin aksamalar', 'incidents.empty': 'Etkin aksama yok.',
    'incidents.retract': 'Geri çek', 'retry': 'Bu çalıştırmayı yeniden dene', 'share': 'Bu çalıştırmanın bağlantısını kopyala', 'copied': 'Bağlantı kopyalandı',
    'language': 'English', 'theme': 'Temayı değiştir', 'round': 'Açıklama turu',
  },
} as const

export type Key = keyof typeof dictionary.en

function initial(): Language {
  try {
    const saved = window.localStorage.getItem('trl-language')
    if (saved === 'en' || saved === 'tr') return saved
  } catch { /* storage can be blocked */ }
  return navigator.language.toLowerCase().startsWith('tr') ? 'tr' : 'en'
}

export function translate(language: Language, key: Key) {
  return dictionary[language][key]
}

export function useLanguage() {
  const [language, setLanguage] = useState<Language>(initial)
  const toggle = useCallback(() => {
    setLanguage(current => {
      const next = current === 'en' ? 'tr' : 'en'
      try { window.localStorage.setItem('trl-language', next) } catch { /* ignore */ }
      document.documentElement.lang = next
      return next
    })
  }, [])
  return { language, toggle, t: (key: Key) => translate(language, key) }
}

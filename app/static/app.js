// Trouve — Je dépose, je retrouve

let currentDocuments = [];
let activeDocument = null;
let searchDebounceTimer = null;
let statusPollInterval = null;
let dragCounter = 0;

let currentViewMode = 'grid'; // 'grid' (tuiles) or 'list' (lignes)
let currentTab = 'categories'; // 'categories' or 'recents'
let currentLang = localStorage.getItem('lazydocs_lang') || 'fr';

const I18N = {
    fr: {
        searchPlaceholder: 'EDF 2025, impôts, assurance voiture, 132 €…',
        categoriesHeader: 'Par Type de document',
        recentsHeader: 'Documents récents',
        breakdownTitle: 'Répartition par type de document',
        typesCount: '{n} types',
        reindexTooltip: 'Reconstruire / Réindexer tout avec l\'IA',
        addTooltip: 'Ajouter',
        addFiles: 'PDF & Photos / Scans',
        addFolder: 'Dossier entier',
        btnReindexAll: 'Réindexer tout',
        reindexStarted: 'La réindexation a été lancée en arrière-plan.',
        dropTitle: 'Déposez vos fichiers ici',
        dropSubtitle: 'PDF & Photos — indexation automatique',
        noDocs: 'Aucun document',
        noDocsSub: 'Déposez vos PDF ici ou cliquez sur + pour commencer.',
        prevPage: '← Précédent',
        nextPage: 'Suivant →',
        pageInfo: 'Page {page} sur {total}'
    },
    en: {
        searchPlaceholder: 'EDF invoice, taxes, car insurance, $132…',
        categoriesHeader: 'By Document Type',
        recentsHeader: 'Recent Documents',
        breakdownTitle: 'Breakdown by Document Type',
        typesCount: '{n} types',
        reindexTooltip: 'Rebuild / Reindex all with AI',
        addTooltip: 'Add',
        addFiles: 'PDF & Images / Scans',
        addFolder: 'Entire folder',
        btnReindexAll: 'Reindex all',
        reindexStarted: 'Reindexing launched in background.',
        dropTitle: 'Drop your files here',
        dropSubtitle: 'PDF & Images — automatic indexing',
        noDocs: 'No documents',
        noDocsSub: 'Drop your PDFs here or click + to get started.',
        prevPage: '← Previous',
        nextPage: 'Next →',
        pageInfo: 'Page {page} of {total}'
    }
};

const CATEGORY_NAMES_EN = {
    'Bulletin de paie': 'Payslip',
    'Facture': 'Invoice',
    'Avis d\'imposition': 'Tax Return',
    'Taxe': 'Tax Notice',
    'Attestation': 'Certificate / Proof',
    'Assurance': 'Insurance',
    'Relevé de compte': 'Bank Statement',
    'RIB / IBAN': 'Bank Details (RIB/IBAN)',
    'Quittance': 'Rent Receipt',
    'Contrat': 'Contract / Agreement',
    'Devis': 'Estimate / Quote',
    'Courrier': 'Letter / Mail',
    'Justificatif de domicile': 'Proof of Address',
    'Acte de naissance': 'Birth Certificate',
    'Certificat de mariage': 'Marriage Certificate',
    'Livret de famille': 'Family Record Book',
    'Acte de décès': 'Death Certificate',
    'Diplôme': 'Diploma / Degree',
    'Curriculum Vitae': 'Resume / CV',
    'Carte grise': 'Vehicle Registration',
    'Permis de conduire': 'Driver\'s License',
    'Pièce d\'identité': 'ID Card / Passport',
    'Véhicule': 'Vehicle',
    'Logement': 'Housing / Property',
    'Courriers/Administratif': 'Official Mail / Admin',
    'Autre': 'Other'
};

function getCategoryLabel(docType) {
    if (currentLang === 'en') {
        return CATEGORY_NAMES_EN[docType] || docType;
    }
    return docType;
}

function updateUILanguage() {
    const btnFlag = document.getElementById('lang-flag');
    const btnCode = document.getElementById('lang-code');
    if (btnFlag && btnCode) {
        btnFlag.textContent = currentLang === 'en' ? '🇬🇧' : '🇫🇷';
        btnCode.textContent = currentLang.toUpperCase();
    }
    document.documentElement.lang = currentLang;

    const t = I18N[currentLang] || I18N.fr;

    const searchInput = document.getElementById('search-input');
    if (searchInput) searchInput.placeholder = t.searchPlaceholder;

    const tabCategories = document.getElementById('tab-categories');
    if (tabCategories) {
        const span = tabCategories.querySelector('span');
        if (span) span.textContent = t.categoriesHeader;
    }

    const tabRecents = document.getElementById('tab-recents');
    if (tabRecents) {
        const span = tabRecents.querySelector('span');
        if (span) span.textContent = t.recentsHeader;
    }

    const listTitle = document.getElementById('list-title');
    if (listTitle) listTitle.textContent = t.recentsHeader;

    const sectionTitle = document.querySelector('#categories-section .results-title');
    if (sectionTitle) sectionTitle.textContent = t.breakdownTitle;

    if (typeof renderCategories === 'function') renderCategories();
    if (typeof renderDocumentList === 'function') renderDocumentList(currentDocuments);
}

const CATEGORY_CONFIG = {
    // Financial / Invoicing
    'Factures': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="12" y2="14"/></svg>',
        color: '#059669'
    },
    'Facture': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="12" y2="14"/></svg>',
        color: '#059669'
    },
    'Devis': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
        color: '#d97706'
    },
    'Banque': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>',
        color: '#0284c7'
    },
    'Relevé de compte': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>',
        color: '#0284c7'
    },
    'RIB / IBAN': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>',
        color: '#0284c7'
    },
    // Work / Employment
    'Travail': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
        color: '#7c3aed'
    },
    'Bulletin de paie': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
        color: '#7c3aed'
    },
    'Curriculum Vitae': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><circle cx="10" cy="9" r="2"/><path d="M6 17c0-2 2-3 4-3s4 1 4 3"/></svg>',
        color: '#6366f1'
    },
    'CV': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><circle cx="10" cy="9" r="2"/><path d="M6 17c0-2 2-3 4-3s4 1 4 3"/></svg>',
        color: '#6366f1'
    },
    // Taxes
    'Impôts/Taxes': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"/><polyline points="14 2 14 8 20 8"/><path d="M2 15h10"/><path d="m9 18 3-3-3-3"/></svg>',
        color: '#4f46e5'
    },
    'Avis d\'imposition': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"/><polyline points="14 2 14 8 20 8"/><path d="M2 15h10"/><path d="m9 18 3-3-3-3"/></svg>',
        color: '#4f46e5'
    },
    'Taxe': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"/><polyline points="14 2 14 8 20 8"/><path d="M2 15h10"/><path d="m9 18 3-3-3-3"/></svg>',
        color: '#4f46e5'
    },
    // Legal & Agreements
    'Contrats': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18l-2-2 4-4"/></svg>',
        color: '#2563eb'
    },
    'Contrat': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18l-2-2 4-4"/></svg>',
        color: '#2563eb'
    },
    'Assurance': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        color: '#0891b2'
    },
    'Attestation': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
        color: '#8b5cf6'
    },
    'Quittance': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        color: '#10b981'
    },
    'Courrier': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 7 12 13 2 7"/></svg>',
        color: '#64748b'
    },
    // Identity
    'Identité': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M15 8h2M15 12h2M7 16h10"/></svg>',
        color: '#3b82f6'
    },
    'Pièce d\'identité': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M15 8h2M15 12h2M7 16h10"/></svg>',
        color: '#3b82f6'
    },
    'Permis de conduire': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M15 8h2M15 12h2M7 16h10"/></svg>',
        color: '#0284c7'
    },
    'Carte grise': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 11 2 11.5 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>',
        color: '#0ea5e9'
    },
    'Justificatif de domicile': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        color: '#16a34a'
    },
    // Vital records / Civil status
    'État civil': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        color: '#ec4899'
    },
    'Acte de naissance': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
        color: '#f43f5e'
    },
    'Certificat de mariage': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/></svg>',
        color: '#d946ef'
    },
    'Livret de famille': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
        color: '#a855f7'
    },
    'Acte de décès': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>',
        color: '#64748b'
    },
    // Medical / Healthcare
    'Médical': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M12 8v6M9 11h6"/></svg>',
        color: '#e11d48'
    },
    'Document de santé': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M12 8v6M9 11h6"/></svg>',
        color: '#e11d48'
    },
    // School / Education
    'Scolarité': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
        color: '#0284c7'
    },
    'Diplôme': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
        color: '#2563eb'
    },
    // Vehicle
    'Véhicule': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 11 2 11.5 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>',
        color: '#ea580c'
    },
    'Véhicules': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 11 2 11.5 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>',
        color: '#ea580c'
    },
    // Housing / Property
    'Logement': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        color: '#059669'
    },
    'Logements': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        color: '#059669'
    },
    // Mail / Administrative
    'Courriers/Administratif': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 7 12 13 2 7"/></svg>',
        color: '#8b5cf6'
    },
    'Courrier': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 7 12 13 2 7"/></svg>',
        color: '#8b5cf6'
    },
    'Administratif': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22 7 12 13 2 7"/></svg>',
        color: '#8b5cf6'
    },
    // Default
    'Autre': {
        icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>',
        color: '#6b7280'
    }
};

function getCategoryConfig(type) {
    if (!type) return CATEGORY_CONFIG['Autre'];
    if (CATEGORY_CONFIG[type]) return CATEGORY_CONFIG[type];

    const clean = type.trim().toLowerCase();
    for (const [key, cfg] of Object.entries(CATEGORY_CONFIG)) {
        if (key.toLowerCase() === clean) return cfg;
    }
    // Partial substring fallback
    if (clean.includes('factur')) return CATEGORY_CONFIG['Factures'];
    if (clean === 'cv' || clean.includes('curriculum')) return CATEGORY_CONFIG['CV'];
    if (clean.includes('paie') || clean.includes('salair')) return CATEGORY_CONFIG['Bulletin de paie'];
    if (clean.includes('travail') || clean.includes('emploi')) return CATEGORY_CONFIG['Travail'];
    if (clean.includes('impôt') || clean.includes('taxe')) return CATEGORY_CONFIG['Impôts/Taxes'];
    if (clean.includes('santé') || clean.includes('médic')) return CATEGORY_CONFIG['Médical'];
    if (clean.includes('scol') || clean.includes('diplôm') || clean.includes('étude')) return CATEGORY_CONFIG['Scolarité'];
    if (clean.includes('identit') || clean.includes('permis') || clean.includes('passeport')) return CATEGORY_CONFIG['Identité'];
    if (clean.includes('état civil') || clean.includes('naiss') || clean.includes('mariag') || clean.includes('décès')) return CATEGORY_CONFIG['État civil'];
    if (clean.includes('contrat') || clean.includes('assur')) return CATEGORY_CONFIG['Contrats'];
    if (clean.includes('banq') || clean.includes('rib') || clean.includes('relevé')) return CATEGORY_CONFIG['Banque'];
    if (clean.includes('véhicul') || clean.includes('vehicul') || clean.includes('auto') || clean.includes('voitur')) return CATEGORY_CONFIG['Véhicule'];
    if (clean.includes('logement') || clean.includes('habitat') || clean.includes('immobili') || clean.includes('quittance')) return CATEGORY_CONFIG['Logement'];
    if (clean.includes('courrier') || clean.includes('administratif') || clean.includes('amende')) return CATEGORY_CONFIG['Courriers/Administratif'];

    return CATEGORY_CONFIG['Autre'];
}

// SVG templates (no emojis)
const SVG = {
    file: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>',
    open: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
    settings: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    trash: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>'
};

// DOM
const searchInput = document.getElementById('search-input');
const btnClearSearch = document.getElementById('btn-clear-search');
const searchStats = document.getElementById('search-stats');
const documentList = document.getElementById('document-list');
const emptyState = document.getElementById('empty-state');
const listTitle = document.getElementById('list-title');
const btnRefresh = document.getElementById('btn-refresh');
const toastEl = document.getElementById('toast');
const statusIndicator = document.getElementById('status-indicator');
const statusIndicatorText = document.getElementById('status-indicator-text');
const fileInputHeader = document.getElementById('file-input-header');
const fileInputHero = document.getElementById('file-input-hero');
const fabFileInput = document.getElementById('fab-file-input');
const dragOverlay = document.getElementById('drag-overlay');
const detailModal = document.getElementById('detail-modal');
const detailFilename = document.getElementById('detail-filename');
const detailStatus = document.getElementById('detail-status');
const detailPerson = document.getElementById('detail-person');
const detailOrg = document.getElementById('detail-org');
const detailType = document.getElementById('detail-type');
const detailDate = document.getElementById('detail-date');
const detailAmount = document.getElementById('detail-amount');
const detailTagsList = document.getElementById('detail-tags-list');
const tagInput = document.getElementById('tag-input');
const btnAddTag = document.getElementById('btn-add-tag');
const detailText = document.getElementById('detail-text');
const btnModalOpenPdf = document.getElementById('btn-modal-open-pdf');
const btnSaveMeta = document.getElementById('btn-save-meta');
const btnDeleteDoc = document.getElementById('btn-delete-doc');

document.addEventListener('DOMContentLoaded', () => {
    updateUILanguage();
    setupTabNavigation();
    fetchCategoryTiles();
    fetchDocuments();
    setupEventListeners();
    setupDragAndDrop();
    checkStatus();
    startPolling();
    initPWA();
});

function initPWA() {
    // 1. Service Worker registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').then(() => {
            console.log('LazyDocs PWA Service Worker active.');
        }).catch(err => {
            console.warn('PWA SW registration error:', err);
        });
    }

    // 2. Detect shared document via Web Share Target (?shared=1)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('shared') === '1') {
        showToast('📱 Mobile document received and queued for indexing!');
        // Clean URL query parameters
        window.history.replaceState({}, document.title, window.location.pathname);
        checkStatus();
        setTimeout(() => fetchDocuments(), 1200);
    }
}

function setupTabNavigation() {
    const tabCategories = document.getElementById('tab-categories');
    const tabRecents = document.getElementById('tab-recents');
    const secCategories = document.getElementById('categories-section');
    const secDocuments = document.getElementById('documents-section');
    const btnViewGrid = document.getElementById('btn-view-grid');
    const btnViewList = document.getElementById('btn-view-list');

    if (tabCategories && tabRecents) {
        tabCategories.onclick = () => {
            currentTab = 'categories';
            tabCategories.classList.add('active');
            tabRecents.classList.remove('active');
            if (secCategories && secDocuments) {
                secCategories.classList.remove('hidden');
                secDocuments.classList.add('hidden');
            }
            if (searchInput) searchInput.value = '';
            if (btnClearSearch) btnClearSearch.classList.add('hidden');
            if (searchStats) searchStats.classList.add('hidden');
            fetchCategoryTiles();
        };

        tabRecents.onclick = () => {
            currentTab = 'recents';
            tabRecents.classList.add('active');
            tabCategories.classList.remove('active');
            if (secCategories && secDocuments) {
                secCategories.classList.add('hidden');
                secDocuments.classList.remove('hidden');
            }
            if (searchInput) searchInput.value = '';
            if (btnClearSearch) btnClearSearch.classList.add('hidden');
            if (searchStats) searchStats.classList.add('hidden');
            fetchDocuments();
        };
    }

    if (btnViewGrid && btnViewList) {
        btnViewGrid.onclick = () => {
            currentViewMode = 'grid';
            btnViewGrid.classList.add('active');
            btnViewList.classList.remove('active');
            renderList(currentDocuments);
        };

        btnViewList.onclick = () => {
            currentViewMode = 'list';
            btnViewList.classList.add('active');
            btnViewGrid.classList.remove('active');
            renderList(currentDocuments);
        };
    }
}

async function fetchCategoryTiles() {
    const container = document.getElementById('category-tiles-grid');
    const totalTypesEl = document.getElementById('total-types-count');
    if (!container) return;

    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();
        const breakdown = data.type_breakdown || [];
        const countsMap = {};
        breakdown.forEach(item => { if (item.count > 0) countsMap[item.type] = item.count; });

        const categoriesList = Object.keys(countsMap).map(t => ({
            type: t,
            count: countsMap[t]
        })).filter(c => c.count > 0).sort((a, b) => b.count - a.count);

        if (totalTypesEl) {
            totalTypesEl.textContent = `${categoriesList.length} type(s) disponible(s)`;
        }

        if (categoriesList.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 48px 20px; color: var(--text-3);">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 12px; opacity: 0.4;"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                    <p style="font-size: 15px; font-weight: 600; color: var(--text-2); margin-bottom: 4px;">Aucune catégorie active</p>
                    <p style="font-size: 13px;">Déposez vos premiers documents pour créer automatiquement les catégories.</p>
                </div>
            `;
            return;
        }

        const maxCount = Math.max(...categoriesList.map(c => c.count), 1);

        container.innerHTML = '';
        categoriesList.forEach(cat => {
            const cfg = getCategoryConfig(cat.type);
            const card = document.createElement('div');
            card.className = 'category-card';

            const pct = Math.round((cat.count / maxCount) * 100);

            card.innerHTML = `
                <div class="category-card-top">
                    <div class="category-icon-wrapper" style="background: ${cfg.color}15; color: ${cfg.color};">
                        ${cfg.icon}
                    </div>
                    <span class="category-count-pill">${cat.count} doc(s)</span>
                </div>
                <div class="category-card-body">
                    <span class="category-title">${esc(getCategoryLabel(cat.type))}</span>
                    <div class="category-progress-track">
                        <div class="category-progress-fill" style="width: ${pct}%; background: ${cfg.color};"></div>
                    </div>
                </div>
            `;

            card.onclick = () => {
                const secCategories = document.getElementById('categories-section');
                const secDocuments = document.getElementById('documents-section');
                if (secCategories && secDocuments) {
                    secCategories.classList.add('hidden');
                    secDocuments.classList.remove('hidden');
                }
                const tabCategories = document.getElementById('tab-categories');
                const tabRecents = document.getElementById('tab-recents');
                if (tabCategories) tabCategories.classList.remove('active');
                if (tabRecents) tabRecents.classList.add('active');

                currentViewMode = 'grid';
                const btnViewGrid = document.getElementById('btn-view-grid');
                const btnViewList = document.getElementById('btn-view-list');
                if (btnViewGrid) btnViewGrid.classList.add('active');
                if (btnViewList) btnViewList.classList.remove('active');

                if (searchInput) {
                    searchInput.value = cat.type;
                    if (btnClearSearch) btnClearSearch.classList.remove('hidden');
                }
                performSearch(cat.type);
            };

            container.appendChild(card);
        });

    } catch (e) {
        console.error('Erreur lors du chargement des tuiles par type:', e);
    }
}

function setupEventListeners() {
    const btnLangToggle = document.getElementById('btn-lang-toggle');
    if (btnLangToggle) {
        btnLangToggle.addEventListener('click', () => {
            currentLang = currentLang === 'fr' ? 'en' : 'fr';
            localStorage.setItem('lazydocs_lang', currentLang);
            updateUILanguage();
        });
    }

    searchInput.addEventListener('input', (e) => {
        const q = e.target.value.trim();
        btnClearSearch.classList.toggle('hidden', !q);
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            if (q.length > 0) {
                performSearch(q);
            } else {
                const tabCategories = document.getElementById('tab-categories');
                if (tabCategories) tabCategories.click();
            }
        }, 200);
    });

    btnClearSearch.addEventListener('click', () => {
        searchInput.value = '';
        btnClearSearch.classList.add('hidden');
        searchStats.classList.add('hidden');
        const tabCategories = document.getElementById('tab-categories');
        if (tabCategories) tabCategories.click();
    });

    const btnRefresh = document.getElementById('btn-refresh');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            searchInput.value.trim() ? performSearch(searchInput.value.trim()) : fetchDocuments();
            checkStatus();
        });
    }

    const btnCancelIndex = document.getElementById('btn-cancel-index');
    if (btnCancelIndex) {
        btnCancelIndex.addEventListener('click', async () => {
            if (confirm('Voulez-vous stopper l\'indexation en cours ?')) {
                try {
                    const res = await fetch('/api/cancel-indexing', { method: 'POST' });
                    const data = await res.json();
                    showToast(data.message || 'Indexation annulée.');
                    checkStatus();
                    refreshCurrentView();
                } catch (e) {
                    showToast('Erreur lors de l\'annulation.');
                }
            }
        });
    }

    const btnReindex = document.getElementById('btn-reindex');
    if (btnReindex) {
        btnReindex.addEventListener('click', async () => {
            if (confirm('Relancer l\'analyse IA sur l\'ensemble de vos documents ?')) {
                try {
                    btnReindex.classList.add('spinning');
                    const res = await fetch('/api/reindex', { method: 'POST' });
                    const data = await res.json();
                    showToast(data.message || 'Réindexation lancée.');
                    checkStatus();
                    setTimeout(() => fetchDocuments(), 1000);
                } catch (e) {
                    showToast('Erreur lors de la réindexation.');
                } finally {
                    setTimeout(() => btnReindex.classList.remove('spinning'), 3000);
                }
            }
        });
    }

    // Dashboard toggle
    const btnDashboard = document.getElementById('btn-dashboard');
    if (btnDashboard) {
        btnDashboard.addEventListener('click', openDashboard);
    }
    const dashModal = document.getElementById('dashboard-modal');
    if (dashModal) {
        dashModal.querySelectorAll('.modal-close, .modal-backdrop').forEach(el => {
            el.onclick = () => dashModal.classList.add('hidden');
        });
    }

    // Add menu dropdown toggle
    const btnAddToggle = document.getElementById('btn-add-toggle');
    const addMenu = document.getElementById('add-menu');
    if (btnAddToggle && addMenu) {
        btnAddToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            addMenu.classList.toggle('hidden');
        });
        document.addEventListener('click', () => {
            addMenu.classList.add('hidden');
        });
    }

    const cameraInputHeader = document.getElementById('camera-input-header');
    [fileInputHeader, cameraInputHeader, fabFileInput].forEach(el => {
        if (el) el.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length) {
                handleUpload(e.target.files);
                e.target.value = '';
            }
        });
    });

    // Directory input — filters to PDF and images from entire folder tree
    const dirInputHeader = document.getElementById('dir-input-header');
    if (dirInputHeader) {
        dirInputHeader.addEventListener('change', (e) => {
            if (!e.target.files || !e.target.files.length) return;
            const validFiles = Array.from(e.target.files).filter(f => {
                const name = f.name.toLowerCase();
                return name.endsWith('.pdf') || name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.webp');
            });
            if (validFiles.length === 0) {
                showToast('Aucun fichier compatible (PDF ou Image) trouvé');
            } else {
                showToast(validFiles.length + ' fichier(s) trouvé(s), envoi en cours…');
                handleUpload(validFiles);
            }
            e.target.value = '';
        });
    }

    document.querySelectorAll('.modal-close, .modal-backdrop').forEach(el => {
        el.addEventListener('click', closeModal);
    });

    btnModalOpenPdf.addEventListener('click', () => {
        if (activeDocument) window.open('/api/documents/' + activeDocument.id + '/file', '_blank');
    });

    const btnReindexDoc = document.getElementById('btn-reindex-doc');
    if (btnReindexDoc) {
        btnReindexDoc.addEventListener('click', async () => {
            if (!activeDocument) return;
            try {
                const res = await fetch('/api/documents/' + activeDocument.id + '/reindex', { method: 'POST' });
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.detail || 'Erreur lors du lancement');
                }
                showToast('Ré-analyse IA lancée…');
                closeModal();
                if (typeof refreshCurrentView === 'function') refreshCurrentView();
                checkStatus();
                startPolling();
            } catch (e) {
                console.error('Erreur relance analyse:', e);
                showToast('Impossible de relancer l\'analyse.');
            }
        });
    }

    // Select All Checkbox
    const selectAllCb = document.getElementById('select-all-checkbox');
    if (selectAllCb) {
        selectAllCb.addEventListener('change', (e) => {
            if (e.target.checked) {
                currentDocuments.forEach(d => selectedDocIds.add(d.id));
            } else {
                selectedDocIds.clear();
            }
            document.querySelectorAll('#document-list .select-checkbox').forEach(cb => {
                cb.checked = e.target.checked;
            });
            updateBatchUI();
        });
    }

    // Batch Delete Button
    const btnBatchDelete = document.getElementById('btn-batch-delete');
    if (btnBatchDelete) {
        btnBatchDelete.addEventListener('click', async () => {
            const count = selectedDocIds.size;
            if (count === 0) return;
            if (!confirm(`Supprimer définitivement ${count} document(s) sélectionné(s) ?`)) return;

            const ids = Array.from(selectedDocIds);
            const queryStr = ids.map(id => 'doc_ids=' + encodeURIComponent(id)).join('&');
            try {
                const res = await fetch('/api/documents?' + queryStr, { method: 'DELETE' });
                if (!res.ok) throw new Error();
                showToast(`${count} document(s) supprimé(s)`);
                selectedDocIds.clear();
                refreshCurrentView();
                checkStatus();
            } catch (err) {
                alert('Erreur lors de la suppression en masse.');
            }
        });
    }

    // Pagination buttons
    const btnPrevPage = document.getElementById('btn-prev-page');
    const btnNextPage = document.getElementById('btn-next-page');

    if (btnPrevPage) {
        btnPrevPage.addEventListener('click', () => {
            if (currentPage > 1) {
                fetchDocuments(currentPage - 1);
            }
        });
    }

    if (btnNextPage) {
        btnNextPage.addEventListener('click', () => {
            if (currentPage < totalPages) {
                fetchDocuments(currentPage + 1);
            }
        });
    }

    btnSaveMeta.addEventListener('click', saveMeta);
    btnDeleteDoc.addEventListener('click', deleteDoc);
    btnAddTag.addEventListener('click', addTag);
    tagInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') addTag(); });
}

function setupDragAndDrop() {
    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (e.dataTransfer.types && (e.dataTransfer.types.includes('Files') || e.dataTransfer.types.includes('application/x-moz-file'))) {
            dragOverlay.classList.remove('hidden');
        }
    });
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) { dragCounter = 0; dragOverlay.classList.add('hidden'); }
    });
    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dragOverlay.classList.add('hidden');
        if (e.dataTransfer.files && e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
    });
}

function closeModal() { detailModal.classList.add('hidden'); activeDocument = null; }

function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    setTimeout(() => toastEl.classList.add('hidden'), 3000);
}

let currentPage = 1;
let totalPages = 1;
let pageLimit = 20;

function refreshCurrentView() {
    const q = searchInput ? searchInput.value.trim() : '';
    if (q) {
        performSearch(q);
    } else {
        fetchDocuments(currentPage);
    }
}


async function fetchDocuments(page = 1) {
    currentPage = page;
    listTitle.textContent = 'Documents récents';
    searchStats.classList.add('hidden');
    try {
        const res = await fetch(`/api/documents?page=${currentPage}&limit=${pageLimit}`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        currentDocuments = data.documents || [];
        totalPages = data.pages || 1;
        renderList(currentDocuments);
        updatePaginationUI(data.page, data.pages, data.total);
    } catch (e) { console.error(e); }
}

async function performSearch(q) {
    const secCategories = document.getElementById('categories-section');
    const secDocuments = document.getElementById('documents-section');
    if (secCategories && secDocuments) {
        secCategories.classList.add('hidden');
        secDocuments.classList.remove('hidden');
    }

    listTitle.textContent = 'Résultats pour « ' + esc(q) + ' »';
    try {
        const res = await fetch('/api/search?q=' + encodeURIComponent(q));
        if (!res.ok) throw new Error();
        const data = await res.json();
        searchStats.textContent = data.total + ' document(s) trouvé(s)';
        searchStats.classList.remove('hidden');
        currentDocuments = data.results;

        // Force grid view when searching (tuiles)
        currentViewMode = 'grid';
        const btnViewGrid = document.getElementById('btn-view-grid');
        const btnViewList = document.getElementById('btn-view-list');
        if (btnViewGrid) btnViewGrid.classList.add('active');
        if (btnViewList) btnViewList.classList.remove('active');

        renderList(currentDocuments);
        hidePaginationUI();
    } catch (e) { console.error(e); }
}

function updatePaginationUI(page, pages, total) {
    const container = document.getElementById('pagination-container');
    const info = document.getElementById('pagination-info');
    const btnPrev = document.getElementById('btn-prev-page');
    const btnNext = document.getElementById('btn-next-page');

    if (!container || total === 0) {
        hidePaginationUI();
        return;
    }

    container.classList.remove('hidden');
    info.textContent = `Page ${page} sur ${pages} (${total} documents)`;

    if (btnPrev) btnPrev.disabled = page <= 1;
    if (btnNext) btnNext.disabled = page >= pages;
}

function hidePaginationUI() {
    const container = document.getElementById('pagination-container');
    if (container) container.classList.add('hidden');
}

let selectedDocIds = new Set();

function updateBatchUI() {
    const selectAllCb = document.getElementById('select-all-checkbox');
    const btnBatchDelete = document.getElementById('btn-batch-delete');
    const selectedCountEl = document.getElementById('selected-count');

    const totalDocs = currentDocuments.length;
    const selectedCount = selectedDocIds.size;

    if (selectedCountEl) selectedCountEl.textContent = selectedCount;

    if (btnBatchDelete) {
        btnBatchDelete.classList.toggle('hidden', selectedCount === 0);
    }

    if (selectAllCb) {
        selectAllCb.checked = totalDocs > 0 && selectedCount === totalDocs;
        selectAllCb.indeterminate = selectedCount > 0 && selectedCount < totalDocs;
    }
}

function getSmartTitle(doc) {
    const parts = [];
    if (doc.document_type && doc.document_type !== 'Autre') {
        parts.push(getCategoryLabel(doc.document_type));
    }
    if (doc.organization && doc.organization.toLowerCase() !== 'organisme inconnu') {
        parts.push(doc.organization);
    }
    if (parts.length > 0) {
        return parts.join(' — ');
    }
    return doc.filename.replace(/\.[^/.]+$/, "");
}

function renderList(docs) {
    documentList.innerHTML = '';
    selectedDocIds.clear();
    updateBatchUI();

    if (currentViewMode === 'grid') {
        documentList.className = 'doc-grid';
    } else {
        documentList.className = 'doc-list';
    }

    if (!docs || docs.length === 0) { emptyState.classList.remove('hidden'); return; }
    emptyState.classList.add('hidden');

    docs.forEach(doc => {
        if (currentViewMode === 'grid') {
            documentList.appendChild(createDocCard(doc));
        } else {
            documentList.appendChild(createDocRow(doc));
        }
    });
}

function createDocCard(doc) {
    const card = document.createElement('div');
    card.className = 'doc-card';
    card.onclick = () => window.open('/api/documents/' + doc.id + '/file', '_blank');

    // ── Preview thumbnail ──────────────────────────────────────────────
    const preview = document.createElement('div');
    preview.className = 'doc-card-preview';

    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = 'Aperçu';
    img.onerror = () => {
        // On error, show placeholder icon instead
        preview.innerHTML = '';
        const ph = document.createElement('div');
        ph.className = 'doc-card-preview-placeholder';
        const cfg2 = getCategoryConfig(doc.document_type);
        ph.innerHTML = `<div style="color:${cfg2.color}; opacity:0.4;">${cfg2.icon.replace('width="24"','width="40"').replace('height="24"','height="40"')}</div><span>${getCategoryLabel(doc.document_type) || 'Document'}</span>`;
        preview.appendChild(ph);
    };
    img.src = '/api/documents/' + doc.id + '/thumbnail?v=' + Date.now();
    preview.appendChild(img);
    card.appendChild(preview);

    // ── Content wrapper ─────────────────────────────────────────────────
    const content = document.createElement('div');
    content.className = 'doc-card-content';

    // Header
    const header = document.createElement('div');
    header.className = 'doc-card-header';

    const iconTitle = document.createElement('div');
    iconTitle.className = 'doc-card-icon-title';

    const icon = document.createElement('div');
    icon.className = 'doc-card-icon';
    const cfg = getCategoryConfig(doc.document_type);
    icon.innerHTML = cfg ? cfg.icon : SVG.file;
    if (cfg && cfg.color) {
        icon.style.color = cfg.color;
        icon.style.background = cfg.color + '15';
    }

    const titles = document.createElement('div');
    titles.className = 'doc-card-titles';

    const smartTitle = getSmartTitle(doc);
    const name = document.createElement('div');
    name.className = 'doc-card-name';
    name.textContent = smartTitle;
    name.title = smartTitle;

    const sub = document.createElement('div');
    sub.className = 'doc-card-subfilename';
    sub.textContent = doc.filename;

    titles.appendChild(name);
    titles.appendChild(sub);

    iconTitle.appendChild(icon);
    iconTitle.appendChild(titles);

    // Checkbox
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'select-checkbox';
    cb.checked = selectedDocIds.has(doc.id);
    cb.onclick = (e) => {
        e.stopPropagation();
        if (cb.checked) {
            selectedDocIds.add(doc.id);
        } else {
            selectedDocIds.delete(doc.id);
        }
        updateBatchUI();
    };

    header.appendChild(iconTitle);
    header.appendChild(cb);
    content.appendChild(header);

    // Body
    const body = document.createElement('div');
    body.className = 'doc-card-body';

    if (doc.snippet) {
        const snip = document.createElement('div');
        snip.className = 'doc-card-snippet';
        snip.innerHTML = doc.snippet;
        body.appendChild(snip);
    }

    const meta = document.createElement('div');
    meta.className = 'doc-card-meta';

    if (doc.document_type) {
        meta.appendChild(makePill(getCategoryLabel(doc.document_type)));
    }
    if (doc.person_name && !doc.person_name.toLowerCase().includes('inconnu')) {
        meta.appendChild(makePill(doc.person_name));
    }
    const dateStr = doc.document_date || doc.created_at;
    if (dateStr) {
        const yearMatch = dateStr.match(/\d{4}/);
        if (yearMatch) {
            meta.appendChild(makePill(yearMatch[0]));
        }
    }
    body.appendChild(meta);
    content.appendChild(body);

    // Footer
    const footer = document.createElement('div');
    footer.className = 'doc-card-footer';

    const statusWrap = document.createElement('div');
    if (doc.ocr_status !== 'ready') {
        const statusPill = document.createElement('span');
        statusPill.className = 'status-pill status-' + doc.ocr_status;
        statusPill.textContent = doc.ocr_status;
        statusWrap.appendChild(statusPill);
    }

    const actions = document.createElement('div');
    actions.className = 'doc-card-actions';

    const btnDetails = document.createElement('button');
    btnDetails.className = 'row-btn';
    btnDetails.innerHTML = SVG.settings;
    btnDetails.title = 'Détails';
    btnDetails.onclick = (e) => {
        e.stopPropagation();
        openDetail(doc.id);
    };

    actions.appendChild(btnDetails);

    footer.appendChild(statusWrap);
    footer.appendChild(actions);
    content.appendChild(footer);

    card.appendChild(content);
    return card;
}

function createDocRow(doc) {
    const row = document.createElement('div');
    row.className = 'doc-row';

    // Checkbox
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'select-checkbox';
    cb.checked = selectedDocIds.has(doc.id);
    cb.onclick = (e) => {
        e.stopPropagation();
        if (cb.checked) {
            selectedDocIds.add(doc.id);
        } else {
            selectedDocIds.delete(doc.id);
        }
        updateBatchUI();
    };
    row.appendChild(cb);

    // Icon
    const icon = document.createElement('div');
    icon.className = 'doc-row-icon';
    icon.innerHTML = SVG.file;

    // Body
    const body = document.createElement('div');
    body.className = 'doc-row-body';

    const smartTitle = getSmartTitle(doc);
    const name = document.createElement('div');
    name.className = 'doc-row-name';
    name.textContent = smartTitle;
    name.title = smartTitle;
    body.appendChild(name);

    // Subtitle: Original filename in small gray
    const sub = document.createElement('div');
    sub.className = 'doc-row-subfilename';
    sub.textContent = doc.filename;
    body.appendChild(sub);

    if (doc.snippet) {
        const snip = document.createElement('div');
        snip.className = 'doc-row-snippet';
        snip.innerHTML = doc.snippet;
        body.appendChild(snip);
    }

    // Meta pills: Person Name + Year
    const meta = document.createElement('div');
    meta.className = 'doc-row-meta';

    if (doc.person_name && !doc.person_name.toLowerCase().includes('inconnu')) {
        meta.appendChild(makePill(doc.person_name));
    }

    const dateStr = doc.document_date || doc.created_at;
    if (dateStr) {
        const yearMatch = dateStr.match(/\d{4}/);
        if (yearMatch) {
            meta.appendChild(makePill(yearMatch[0]));
        }
    }

    // Status (display only when processing/pending or error, hide when ready)
    const statusWrap = document.createElement('div');
    statusWrap.className = 'doc-row-status';
    if (doc.ocr_status !== 'ready') {
        const statusPill = document.createElement('span');
        statusPill.className = 'status-pill status-' + doc.ocr_status;
        statusPill.textContent = doc.ocr_status;
        statusWrap.appendChild(statusPill);
    }

    // Actions (visible on hover: Détails button only)
    const actions = document.createElement('div');
    actions.className = 'doc-row-actions';

    const btnDetails = document.createElement('button');
    btnDetails.className = 'row-btn';
    btnDetails.innerHTML = SVG.settings;
    btnDetails.title = 'Détails';
    btnDetails.onclick = (e) => { e.stopPropagation(); openDetail(doc.id); };

    actions.appendChild(btnDetails);

    row.appendChild(icon);
    row.appendChild(body);
    row.appendChild(meta);
    row.appendChild(statusWrap);
    row.appendChild(actions);

    row.onclick = () => window.open('/api/documents/' + doc.id + '/file', '_blank');
    return row;
}

function makePill(text) {
    const el = document.createElement('span');
    el.className = 'meta-pill';
    el.textContent = text;
    return el;
}

async function openDetail(docId) {
    try {
        const res = await fetch('/api/documents/' + docId);
        if (!res.ok) throw new Error('Erreur HTTP ' + res.status);
        activeDocument = await res.json();
        if (detailFilename) detailFilename.textContent = activeDocument.filename;
        if (detailStatus) {
            detailStatus.textContent = activeDocument.ocr_status;
            detailStatus.className = 'status-pill status-' + activeDocument.ocr_status;
            if (activeDocument.ocr_status !== 'ready') {
                detailStatus.classList.remove('hidden');
            } else {
                detailStatus.classList.add('hidden');
            }
        }
        if (detailPerson) detailPerson.value = activeDocument.person_name || '';
        if (detailOrg) detailOrg.value = activeDocument.organization || '';
        if (detailType) detailType.value = activeDocument.document_type || '';
        if (detailDate) detailDate.value = activeDocument.document_date || '';

        const fieldAmount = document.getElementById('field-amount');
        if (fieldAmount && detailAmount) {
            if (activeDocument.amount !== null && activeDocument.amount !== undefined && activeDocument.amount !== 0) {
                detailAmount.value = activeDocument.amount;
                fieldAmount.classList.remove('hidden');
            } else {
                detailAmount.value = '';
                fieldAmount.classList.add('hidden');
            }
        }
        if (detailText) detailText.value = activeDocument.content || '';
        renderTags(activeDocument.tags);
        renderRawMetadata(activeDocument.raw_metadata);
        if (detailModal) detailModal.classList.remove('hidden');
    } catch (e) {
        console.error('Erreur openDetail:', e);
        alert('Impossible de charger le document.');
    }
}

function renderRawMetadata(rawMetaStr) {
    const container = document.getElementById('detail-raw-meta');
    const wrapper = document.getElementById('field-raw-meta');
    if (!container || !wrapper) return;

    container.innerHTML = '';
    if (!rawMetaStr) {
        wrapper.classList.add('hidden');
        return;
    }

    try {
        const data = typeof rawMetaStr === 'string' ? JSON.parse(rawMetaStr) : rawMetaStr;
        
        // Liste des clés de base déjà affichées dans les champs principaux du haut
        const primaryKeys = new Set([
            'organization', 'document_date', 'amount', 'type', 'person_name',
            'organisme', 'emetteur', 'expediteur', 'bailleur', 'banque', 'employeur', 'compagnie_assurance',
            'total_ttc', 'net_a_payer', 'montant_impot', 'montant_loyer', 'montant_taxe', 'montant_cotisation', 'solde_final', 'montant',
            'mairie_organisme', 'etablissement', 'nom_salarie', 'nom_personne', 'nom_defunt', 'noms_epoux',
            'nom_titulaire', 'nom_candidat', 'titulaire_compte', 'beneficiaire', 'client', 'redevable', 'assure',
            'personne_concernee', 'titulaire_contrat', 'titulaire'
        ]);

        const extraKeys = Object.keys(data).filter(k => 
            !primaryKeys.has(k.toLowerCase()) &&
            data[k] !== null && data[k] !== undefined && data[k] !== ''
        );

        if (extraKeys.length === 0) {
            wrapper.classList.add('hidden');
            return;
        }

        extraKeys.forEach(k => {
            const item = document.createElement('div');
            item.className = 'raw-meta-item';

            const keyEl = document.createElement('span');
            keyEl.className = 'raw-meta-key';
            keyEl.textContent = k.replace(/_/g, ' ');

            const valEl = document.createElement('span');
            valEl.className = 'raw-meta-val';
            valEl.textContent = typeof data[k] === 'object' ? JSON.stringify(data[k]) : String(data[k]);

            item.appendChild(keyEl);
            item.appendChild(valEl);
            container.appendChild(item);
        });

        wrapper.classList.remove('hidden');
    } catch (e) {
        wrapper.classList.add('hidden');
    }
}

function renderTags(tags) {
    detailTagsList.innerHTML = '';
    (tags || []).forEach(t => {
        const chip = document.createElement('span');
        chip.className = 'tag-chip';
        chip.innerHTML = esc(t) + ' <span class="tag-chip-remove" data-tag="' + esc(t) + '">&times;</span>';
        chip.querySelector('.tag-chip-remove').onclick = () => removeTag(t);
        detailTagsList.appendChild(chip);
    });
}

async function addTag() {
    if (!activeDocument) return;
    const name = tagInput.value.trim();
    if (!name) return;
    try {
        const res = await fetch('/api/documents/' + activeDocument.id + '/tags', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})
        });
        if (!res.ok) throw new Error();
        activeDocument.tags = await res.json();
        renderTags(activeDocument.tags);
        tagInput.value = '';
    } catch (e) { console.error(e); }
}

async function removeTag(name) {
    if (!activeDocument) return;
    try {
        const res = await fetch('/api/documents/' + activeDocument.id + '/tags/' + encodeURIComponent(name), {method: 'DELETE'});
        if (!res.ok) throw new Error();
        activeDocument.tags = await res.json();
        renderTags(activeDocument.tags);
    } catch (e) { console.error(e); }
}

async function saveMeta() {
    if (!activeDocument) return;
    const payload = {
        person_name: detailPerson ? (detailPerson.value.trim() || null) : null,
        organization: detailOrg.value.trim() || null,
        document_type: detailType.value.trim() || null,
        document_date: detailDate.value || null,
        amount: detailAmount.value ? parseFloat(detailAmount.value) : null
    };
    try {
        const res = await fetch('/api/documents/' + activeDocument.id, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error();
        activeDocument = await res.json();
        showToast('Métadonnées enregistrées');
        refreshCurrentView();
    } catch (e) { alert('Erreur lors de la sauvegarde.'); }
}

async function deleteDocById(docId) {
    try {
        const res = await fetch('/api/documents/' + docId, {method: 'DELETE'});
        if (!res.ok) throw new Error();
        showToast('Document supprimé');
        refreshCurrentView();
        checkStatus();
    } catch (e) { alert('Erreur lors de la suppression.'); }
}

async function deleteDoc() {
    if (!activeDocument) return;
    if (!confirm('Supprimer définitivement « ' + activeDocument.filename + ' » ?')) return;
    deleteDocById(activeDocument.id);
    closeModal();
}

async function handleUpload(files) {
    if (!files || !files.length) return;
    const fd = new FormData();
    for (let i = 0; i < files.length; i++) fd.append('files', files[i]);
    showToast('Envoi en cours…');
    try {
        const res = await fetch('/api/documents', {method: 'POST', body: fd});
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Erreur'); }
        const uploaded = await res.json();
        const duplicates = uploaded.filter(d => d.is_duplicate);
        const added = uploaded.filter(d => !d.is_duplicate);

        if (currentLang === 'en') {
            if (added.length > 0 && duplicates.length > 0) {
                showToast(`${added.length} added, ${duplicates.length} duplicate(s) ignored`);
            } else if (duplicates.length > 0) {
                showToast(`⚠️ ${duplicates.length} document(s) already exist (ignored)`);
            } else {
                showToast(`${added.length} document(s) added`);
            }
        } else {
            if (added.length > 0 && duplicates.length > 0) {
                showToast(`${added.length} ajouté(s), ${duplicates.length} doublon(s) ignoré(s)`);
            } else if (duplicates.length > 0) {
                showToast(`⚠️ ${duplicates.length} document(s) déjà présent(s) (doublon ignoré)`);
            } else {
                showToast(`${added.length} document(s) ajouté(s)`);
            }
        }
        refreshCurrentView();
        checkStatus();
    } catch (e) { alert('Erreur : ' + e.message); }
}

async function checkStatus() {
    const btnCancelIndex = document.getElementById('btn-cancel-index');
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        if (data.pending > 0) {
            statusIndicatorText.textContent = data.pending + ' en analyse…';
            statusIndicator.classList.remove('hidden');
            if (btnCancelIndex) btnCancelIndex.classList.remove('hidden');
        } else {
            statusIndicator.classList.add('hidden');
            if (btnCancelIndex) btnCancelIndex.classList.add('hidden');
        }
    } catch (e) { console.error(e); }
}

function startPolling() {
    if (statusPollInterval) return;
    statusPollInterval = setInterval(() => {
        checkStatus();
        if (currentDocuments.some(d => d.ocr_status === 'pending' || d.ocr_status === 'processing')) {
            if (typeof refreshCurrentView === 'function') refreshCurrentView();
        }
    }, 2500);
}

async function openDashboard() {
    const modal = document.getElementById('dashboard-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) throw new Error('Erreur HTTP ' + res.status);
        const data = await res.json();

        const totalDocsEl = document.getElementById('dash-total-docs');
        if (totalDocsEl) totalDocsEl.textContent = data.total_docs || 0;

        const totalOrgsEl = document.getElementById('dash-total-orgs');
        if (totalOrgsEl) totalOrgsEl.textContent = data.total_orgs || 0;

        const totalTypesEl = document.getElementById('dash-total-types');
        if (totalTypesEl) totalTypesEl.textContent = data.total_types || 0;

        const totalAmtEl = document.getElementById('dash-total-amount');
        if (totalAmtEl) {
            const totalAmtStr = (data.total_amount || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
            totalAmtEl.textContent = totalAmtStr;
        }

        // Render type bars
        const barsContainer = document.getElementById('dash-type-bars');
        if (barsContainer) {
            barsContainer.innerHTML = '';
            const maxCount = (data.type_breakdown && data.type_breakdown.length) ? data.type_breakdown[0].count : 1;

            (data.type_breakdown || []).forEach(tb => {
                const pct = Math.round((tb.count / maxCount) * 100);
                const row = document.createElement('div');
                row.className = 'dash-bar-row';
                row.innerHTML = `
                    <div class="dash-bar-meta">
                        <span>${esc(tb.type)}</span>
                        <span>${tb.count} doc(s)</span>
                    </div>
                    <div class="dash-bar-track">
                        <div class="dash-bar-fill" style="width: ${pct}%;"></div>
                    </div>
                `;
                barsContainer.appendChild(row);
            });
        }

        // Render top orgs
        const orgsContainer = document.getElementById('dash-org-chips');
        if (orgsContainer) {
            orgsContainer.innerHTML = '';
            (data.top_orgs || []).forEach(o => {
                const chip = document.createElement('span');
                chip.className = 'tag-chip';
                chip.style.cursor = 'pointer';
                chip.textContent = `${o.organization} (${o.count})`;
                chip.onclick = () => {
                    modal.classList.add('hidden');
                    if (searchInput) searchInput.value = o.organization;
                    performSearch(o.organization);
                };
                orgsContainer.appendChild(chip);
            });
        }
    } catch (e) {
        console.error('Erreur openDashboard:', e);
        alert('Impossible de charger les statistiques.');
    }
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// discovery.js — Career OS Discovery Quality Review Frontend Controller

let allJobs = [];
let humanDecisions = {}; // job_id -> { verdict, counterfactual, priority, opportunity_status, application_status, notes, reviewed_at }
let currentFilteredJobs = [];
let currentJobIndex = 0;

// Filter State Model
const filterState = {
  type: "ALL",          // ALL | direct | adjacent | transferable | unexpected | stretch
  llmRec: "ALL",        // ALL | STRONG_APPLY | APPLY | CONSIDER | LONG_SHOT | SKIP | GATE_REJECTED
  humanReview: "ALL",   // ALL | UNREVIEWED | REVIEWED | RELEVANT | ADJACENT | WEAK | IRRELEVANT
  oppStatus: "ALL",     // ALL | AVAILABLE | EXPIRED | UNKNOWN
  appStatus: "ALL",     // ALL | NOT_APPLIED | READY_TO_APPLY | APPLIED | RECRUITER_CONTACT | INTERVIEW | REJECTED | WITHDRAWN | OFFER
  intent: "ALL",        // ALL | <exact string>
  source: "ALL",        // ALL | indeed | linkedin
  searchQuery: ""       // free-text search
};

// DOM Elements
const typeNav = document.getElementById("typeNav");
const llmRecSelect = document.getElementById("llmRecSelect");
const humanReviewSelect = document.getElementById("humanReviewSelect");
const oppStatusSelect = document.getElementById("oppStatusSelect");
const appStatusSelect = document.getElementById("appStatusSelect");
const intentSelect = document.getElementById("intentSelect");
const sourceSelect = document.getElementById("sourceSelect");
const searchInput = document.getElementById("searchInput");
const resetFiltersBtn = document.getElementById("resetFiltersBtn");
const navigatorCountLabel = document.getElementById("navigatorCountLabel");
const navigatorList = document.getElementById("navigatorList");

// Center Pane Elements
const jobCard = document.getElementById("jobCard");
const jobTypeTag = document.getElementById("jobTypeTag");
const jobIdTag = document.getElementById("jobIdTag");
const jobSourceTag = document.getElementById("jobSourceTag");
const jobLocation = document.getElementById("jobLocation");
const jobSalary = document.getElementById("jobSalary");
const jobTitle = document.getElementById("jobTitle");
const jobCompany = document.getElementById("jobCompany");
const viewJobLink = document.getElementById("viewJobLink");

const provenanceTypePill = document.getElementById("provenanceTypePill");
const provQuery = document.getElementById("provQuery");
const provHypothesis = document.getElementById("provHypothesis");
const provSourceTime = document.getElementById("provSourceTime");
const jobDescription = document.getElementById("jobDescription");

// LLM Fit Elements
const llmRecBadge = document.getElementById("llmRecBadge");
const llmScorePill = document.getElementById("llmScorePill");
const llmRoleFit = document.getElementById("llmRoleFit");
const llmExpFit = document.getElementById("llmExpFit");
const llmTransFit = document.getElementById("llmTransFit");
const llmSenFit = document.getElementById("llmSenFit");
const llmProbObtain = document.getElementById("llmProbObtain");
const llmDiffUpside = document.getElementById("llmDiffUpside");
const llmStrengthsList = document.getElementById("llmStrengthsList");
const llmGapsList = document.getElementById("llmGapsList");
const llmReasoning = document.getElementById("llmReasoning");

// Decision Pane Elements
const decisionStatus = document.getElementById("decisionStatus");
const verdictButtons = document.querySelectorAll(".verdict-btn");
const cfButtons = document.querySelectorAll(".cf-btn");
const priorityButtons = document.querySelectorAll(".priority-btn");
const oppStatusButtons = document.querySelectorAll(".opp-status-btn");
const appStatusButtons = document.querySelectorAll(".app-status-btn");
const humanNotes = document.getElementById("humanNotes");
const saveNextBtn = document.getElementById("saveNextBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

// Header Progress Elements
const globalProgress = document.getElementById("globalProgress");
const queueProgress = document.getElementById("queueProgress");

// Modals
const summaryBtn = document.getElementById("summaryBtn");
const summaryModal = document.getElementById("summaryModal");
const closeSummaryModal = document.getElementById("closeSummaryModal");
const shortcutsBtn = document.getElementById("shortcutsBtn");

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  fetchDiscoveryData();
  setupEventListeners();
  initGmailIntegration();
});

async function fetchDiscoveryData() {
  try {
    const res = await fetch("/api/discovery/data");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    allJobs = data.jobs || [];
    humanDecisions = data.decisions || {};

    populateIntentDropdown();
    updateBadges();
    applyFilters();
  } catch (err) {
    console.error("Failed to load discovery data:", err);
    jobTitle.textContent = "Error loading discovery opportunities";
    jobCompany.textContent = err.message;
  }
}

function populateIntentDropdown() {
  const intents = new Set();
  allJobs.forEach(j => {
    const q = j.provenance && j.provenance.search_query;
    if (q) intents.add(q);
  });

  intentSelect.innerHTML = `<option value="ALL">All Search Intents (${intents.size})</option>`;
  Array.from(intents).sort().forEach(intent => {
    const opt = document.createElement("option");
    opt.value = intent;
    opt.textContent = intent;
    intentSelect.appendChild(opt);
  });
}

function updateBadges() {
  const total = allJobs.length;
  let reviewed = 0;
  const typeCounts = { direct: 0, adjacent: 0, transferable: 0, unexpected: 0, stretch: 0 };

  allJobs.forEach(j => {
    const otype = (j.provenance && j.provenance.opportunity_type || "").toLowerCase();
    if (typeCounts[otype] !== undefined) typeCounts[otype]++;
    if (humanDecisions[j.job_id]) reviewed++;
  });

  const badgeAll = document.getElementById("badgeTypeAll");
  if (badgeAll) badgeAll.textContent = total;
  const bDirect = document.getElementById("badgeTypeDirect");
  if (bDirect) bDirect.textContent = typeCounts.direct;
  const bAdj = document.getElementById("badgeTypeAdjacent");
  if (bAdj) bAdj.textContent = typeCounts.adjacent;
  const bTrans = document.getElementById("badgeTypeTransferable");
  if (bTrans) bTrans.textContent = typeCounts.transferable;
  const bUnexp = document.getElementById("badgeTypeUnexpected");
  if (bUnexp) bUnexp.textContent = typeCounts.unexpected;
  const bStretch = document.getElementById("badgeTypeStretch");
  if (bStretch) bStretch.textContent = typeCounts.stretch;

  globalProgress.textContent = `${reviewed} / ${total}`;
}

function applyFilters() {
  currentFilteredJobs = allJobs.filter(job => {
    const otype = (job.provenance && job.provenance.opportunity_type || "").toLowerCase();
    const query = job.provenance && job.provenance.search_query || "";
    const source = (job.source || "").toLowerCase();
    const decision = humanDecisions[job.job_id];
    const isReviewed = !!decision;
    const verdict = decision ? decision.verdict : null;
    const oppStatus = (decision && decision.opportunity_status) || "UNKNOWN";
    const appStatus = (decision && decision.application_status) || "NOT_APPLIED";

    // 1. Opportunity Type Filter
    if (filterState.type !== "ALL" && otype !== filterState.type.toLowerCase()) return false;

    // 2. LLM Recommendation Filter
    if (filterState.llmRec !== "ALL") {
      if (filterState.llmRec === "GATE_REJECTED") {
        if (!job.gate_failed) return false;
      } else {
        if (job.gate_failed) return false;
        const rec = (job.llm_evaluation && job.llm_evaluation.recommendation || "Skip").toUpperCase().replace(/\s+/g, "_");
        if (rec !== filterState.llmRec) return false;
      }
    }

    // 3. Human Review Filter
    if (filterState.humanReview !== "ALL") {
      if (filterState.humanReview === "UNREVIEWED" && isReviewed) return false;
      if (filterState.humanReview === "REVIEWED" && !isReviewed) return false;
      if (["RELEVANT", "ADJACENT", "WEAK", "IRRELEVANT"].includes(filterState.humanReview)) {
        if (!isReviewed || verdict !== filterState.humanReview) return false;
      }
    }

    // 4. Opportunity Status Filter
    if (filterState.oppStatus !== "ALL" && oppStatus !== filterState.oppStatus) return false;

    // 5. Application Status Filter
    if (filterState.appStatus !== "ALL" && appStatus !== filterState.appStatus) return false;

    // 6. Search Intent Filter
    if (filterState.intent !== "ALL" && query !== filterState.intent) return false;

    // 7. Source Filter
    if (filterState.source !== "ALL" && source !== filterState.source.toLowerCase()) return false;

    // 8. Free-text Search
    if (filterState.searchQuery.trim()) {
      const q = filterState.searchQuery.toLowerCase();
      const matchId = (job.job_id || "").toLowerCase().includes(q);
      const matchTitle = (job.title || "").toLowerCase().includes(q);
      const matchCompany = (job.company || "").toLowerCase().includes(q);
      const matchLoc = (job.location || "").toLowerCase().includes(q);
      const matchNotes = (decision && decision.notes || "").toLowerCase().includes(q);
      if (!matchId && !matchTitle && !matchCompany && !matchLoc && !matchNotes) return false;
    }

    return true;
  });

  currentJobIndex = 0;
  renderNavigator();
  renderCurrentJob();
}

function renderNavigator() {
  navigatorList.innerHTML = "";
  navigatorCountLabel.textContent = `Opportunities (${currentFilteredJobs.length} of ${allJobs.length})`;

  if (currentFilteredJobs.length === 0) {
    navigatorList.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.8125rem;">No matching opportunities</div>`;
    return;
  }

  currentFilteredJobs.forEach((job, idx) => {
    const item = document.createElement("div");
    const decision = humanDecisions[job.job_id];
    const isReviewed = !!decision;
    const isActive = idx === currentJobIndex;
    const oppStatus = (decision && decision.opportunity_status) || "UNKNOWN";
    const appStatus = (decision && decision.application_status) || "NOT_APPLIED";
    
    item.className = `nav-job-item ${isActive ? "active" : ""} ${isReviewed ? "reviewed" : ""}`;
    item.setAttribute("data-job-id", job.job_id);

    const otype = (job.provenance && job.provenance.opportunity_type || "other").toUpperCase();

    // Human review status badge
    let statusHtml = "";
    if (decision) {
      let verdictColor = "var(--accent-emerald)";
      let verdictBg = "rgba(16, 185, 129, 0.15)";
      if (decision.verdict === "ADJACENT") {
        verdictColor = "var(--accent-cyan)";
        verdictBg = "rgba(6, 182, 212, 0.15)";
      } else if (decision.verdict === "WEAK") {
        verdictColor = "var(--accent-amber)";
        verdictBg = "rgba(245, 158, 11, 0.15)";
      } else if (decision.verdict === "IRRELEVANT") {
        verdictColor = "var(--accent-rose)";
        verdictBg = "rgba(244, 63, 94, 0.15)";
      }
      statusHtml = `<span style="font-size: 0.65rem; font-weight: 700; padding: 0.1rem 0.35rem; border-radius: 4px; background: ${verdictBg}; color: ${verdictColor};">✓ ${decision.verdict}</span>`;
    } else {
      statusHtml = `<span style="font-size: 0.65rem; font-weight: 600; padding: 0.1rem 0.35rem; border-radius: 4px; background: rgba(255, 255, 255, 0.05); color: var(--text-muted);">○ UNREVIEWED</span>`;
    }

    // Priority badge (if set)
    let prioHtml = "";
    if (decision && decision.priority) {
      let prioColor = "var(--accent-blue)";
      let prioBg = "rgba(56, 189, 248, 0.15)";
      if (decision.priority === "HIGH") { prioColor = "var(--accent-rose)"; prioBg = "rgba(244, 63, 94, 0.15)"; }
      else if (decision.priority === "MEDIUM") { prioColor = "var(--accent-amber)"; prioBg = "rgba(245, 158, 11, 0.15)"; }
      else if (decision.priority === "LOW") { prioColor = "var(--text-muted)"; prioBg = "rgba(100, 116, 139, 0.15)"; }
      prioHtml = `<span style="font-size: 0.62rem; font-weight: 700; padding: 0.05rem 0.25rem; border-radius: 3px; background: ${prioBg}; color: ${prioColor};">${decision.priority}</span>`;
    }

    // Opportunity status pill (if AVAILABLE or EXPIRED)
    let oppStatusHtml = "";
    if (oppStatus === "AVAILABLE") {
      oppStatusHtml = `<span style="font-size: 0.62rem; font-weight: 700; padding: 0.05rem 0.25rem; border-radius: 3px; background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); border: 1px solid rgba(16, 185, 129, 0.3);">● AVAIL</span>`;
    } else if (oppStatus === "EXPIRED") {
      oppStatusHtml = `<span style="font-size: 0.62rem; font-weight: 700; padding: 0.05rem 0.25rem; border-radius: 3px; background: rgba(244, 63, 94, 0.2); color: var(--accent-rose); border: 1px solid rgba(244, 63, 94, 0.3);">✕ EXP</span>`;
    }

    // Application status pill (if set)
    let appStatusHtml = "";
    if (appStatus && appStatus !== "NOT_APPLIED") {
      let appColor = "var(--accent-blue)";
      let appBg = "rgba(56, 189, 248, 0.2)";
      let appLabel = appStatus.replace(/_/g, " ");
      if (appStatus === "READY_TO_APPLY") { appColor = "var(--accent-violet)"; appBg = "rgba(139, 92, 246, 0.2)"; appLabel = "⚡ READY"; }
      else if (appStatus === "APPLIED") { appColor = "var(--accent-blue)"; appBg = "rgba(56, 189, 248, 0.2)"; appLabel = "✓ APPLIED"; }
      else if (appStatus === "RECRUITER_CONTACT") { appColor = "var(--accent-cyan)"; appBg = "rgba(6, 182, 212, 0.2)"; appLabel = "💬 CONTACT"; }
      else if (appStatus === "INTERVIEW") { appColor = "var(--accent-emerald)"; appBg = "rgba(16, 185, 129, 0.2)"; appLabel = "★ INTERVIEW"; }
      else if (appStatus === "OFFER") { appColor = "var(--accent-amber)"; appBg = "rgba(245, 158, 11, 0.2)"; appLabel = "🏆 OFFER"; }
      else if (appStatus === "REJECTED") { appColor = "var(--accent-rose)"; appBg = "rgba(244, 63, 94, 0.2)"; appLabel = "✕ REJECTED"; }
      else if (appStatus === "WITHDRAWN") { appColor = "var(--text-muted)"; appBg = "rgba(100, 116, 139, 0.2)"; appLabel = "WITHDRAWN"; }
      appStatusHtml = `<span style="font-size: 0.62rem; font-weight: 700; padding: 0.05rem 0.25rem; border-radius: 3px; background: ${appBg}; color: ${appColor};">${appLabel}</span>`;
    }

    // LLM Score badge
    let llmBadgeHtml = "";
    if (job.gate_failed || job.evaluation_status === "GATE_REJECTED") {
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); font-weight: 700; padding: 0.1rem 0.35rem; border-radius: 3px; background: rgba(244, 63, 94, 0.15); color: var(--accent-rose); border: 1px solid rgba(244, 63, 94, 0.3);">GATE REJ</span>`;
    } else if (job.evaluation_status === "FAILED") {
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); font-weight: 700; padding: 0.1rem 0.35rem; border-radius: 3px; background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);">FAILED</span>`;
    } else if (job.llm_evaluation && (job.llm_evaluation.score !== null && job.llm_evaluation.score !== undefined || job.llm_evaluation.overall_score !== null && job.llm_evaluation.overall_score !== undefined)) {
      const rec = job.llm_evaluation.recommendation || "Skip";
      const score = (job.llm_evaluation.score !== null && job.llm_evaluation.score !== undefined) ? job.llm_evaluation.score : job.llm_evaluation.overall_score;
      let badgeStyle = "background: rgba(148, 163, 184, 0.15); color: var(--text-secondary); border: 1px solid rgba(148, 163, 184, 0.3);";
      if (rec === "Strong Apply" || rec === "Apply") {
        badgeStyle = "background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.4);";
      } else if (rec === "Consider") {
        badgeStyle = "background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.4);";
      } else if (rec === "Long Shot") {
        badgeStyle = "background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); font-weight: 600; border: 1px solid rgba(245, 158, 11, 0.4);";
      }
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); padding: 0.1rem 0.35rem; border-radius: 3px; ${badgeStyle}">${rec.toUpperCase()} [${score}]</span>`;
    } else {
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); padding: 0.1rem 0.35rem; border-radius: 3px; background: rgba(245, 158, 11, 0.1); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.25);">PENDING</span>`;
    }

    item.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--accent-blue); font-weight: 700;">${job.job_id}</span>
        <div style="display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap; justify-content: flex-end;">
          ${prioHtml}
          ${oppStatusHtml}
          ${appStatusHtml}
          ${statusHtml}
        </div>
      </div>
      <div style="font-size: 0.8125rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.3;">
        ${escapeHtml(job.title)}
      </div>
      <div style="font-size: 0.72rem; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${escapeHtml(job.company)} • ${escapeHtml(job.location || "India")}
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.15rem;">
        ${llmBadgeHtml}
        <span style="font-size: 0.65rem; font-family: var(--font-mono); padding: 0.05rem 0.3rem; border-radius: 3px; background: var(--bg-hover); color: var(--text-muted);">${otype}</span>
      </div>
    `;

    item.addEventListener("click", () => {
      currentJobIndex = idx;
      renderCurrentJob();
      highlightActiveNavigatorItem();
    });

    navigatorList.appendChild(item);
  });
}

function highlightActiveNavigatorItem() {
  const items = navigatorList.querySelectorAll(".nav-job-item");
  items.forEach((it, idx) => {
    if (idx === currentJobIndex) {
      it.classList.add("active");
      it.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } else {
      it.classList.remove("active");
    }
  });
}

function renderCurrentJob() {
  if (currentFilteredJobs.length === 0 || currentJobIndex < 0 || currentJobIndex >= currentFilteredJobs.length) {
    clearDetailView();
    return;
  }

  const job = currentFilteredJobs[currentJobIndex];
  const otype = (job.provenance && job.provenance.opportunity_type || "direct").toUpperCase();
  const prov = job.provenance || {};

  jobIdTag.textContent = job.job_id;
  jobTypeTag.textContent = (job.job_type || "Full-time").toUpperCase();
  jobSourceTag.textContent = (job.source || "UNKNOWN").toUpperCase();
  jobLocation.textContent = job.location || "India";
  jobSalary.textContent = formatSalary(job);
  jobTitle.textContent = job.title || "Untitled Role";
  jobCompany.textContent = job.company || "Unknown Company";

  if (job.job_url) {
    viewJobLink.href = job.job_url;
    viewJobLink.style.display = "inline-flex";
  } else {
    viewJobLink.style.display = "none";
  }

  // Exact Provenance Display
  provenanceTypePill.textContent = `${otype} OPPORTUNITY`;
  provQuery.textContent = `"${prov.search_query || "N/A"}"`;
  provHypothesis.textContent = `[${prov.hypothesis_id || "hyp_000"}] ${prov.hypothesis_concept || "Capability Hypothesis"}`;
  
  const timeStr = prov.retrieved_at ? new Date(prov.retrieved_at).toLocaleString() : "Recent Run";
  provSourceTime.textContent = `${(job.source || "").toUpperCase()} • Discovered ${timeStr}`;

  // Description
  jobDescription.textContent = job.description || "No full job description provided by source.";

  // LLM Evaluation Section
  const isGateRejected = job.gate_failed || job.evaluation_status === "GATE_REJECTED";
  const isFailed = job.evaluation_status === "FAILED";
  const hasLlmEval = job.llm_evaluation && (job.llm_evaluation.score !== null && job.llm_evaluation.score !== undefined || job.llm_evaluation.recommendation);

  if (hasLlmEval && !isGateRejected && (job.evaluation_status === "EVALUATED" || job.evaluation_status === "REUSED" || !job.evaluation_status)) {
    const ev = job.llm_evaluation;
    const rec = ev.recommendation || "Skip";
    const scoreVal = (ev.score !== null && ev.score !== undefined) ? ev.score : ev.overall_score;
    const isReused = ev.is_reused || job.evaluation_status === "REUSED";

    llmRecBadge.textContent = isReused ? `${rec.toUpperCase()} (REUSED)` : rec.toUpperCase();
    if (rec === "Strong Apply" || rec === "Apply") {
      llmRecBadge.style.background = "rgba(16, 185, 129, 0.2)";
      llmRecBadge.style.color = "var(--accent-emerald)";
      llmRecBadge.style.borderColor = "var(--accent-emerald)";
    } else if (rec === "Consider") {
      llmRecBadge.style.background = "rgba(56, 189, 248, 0.2)";
      llmRecBadge.style.color = "var(--accent-blue)";
      llmRecBadge.style.borderColor = "var(--accent-blue)";
    } else if (rec === "Long Shot") {
      llmRecBadge.style.background = "rgba(245, 158, 11, 0.2)";
      llmRecBadge.style.color = "var(--accent-amber)";
      llmRecBadge.style.borderColor = "var(--accent-amber)";
    } else {
      llmRecBadge.style.background = "rgba(148, 163, 184, 0.2)";
      llmRecBadge.style.color = "var(--text-secondary)";
      llmRecBadge.style.borderColor = "var(--border-color)";
    }

    llmScorePill.textContent = (scoreVal !== null && scoreVal !== undefined) ? `SCORE: ${scoreVal}/100` : `SCORE: —`;
    llmRoleFit.textContent = (ev.role_fit !== null && ev.role_fit !== undefined) ? `${ev.role_fit}/100` : `—`;
    llmExpFit.textContent = (ev.current_experience_fit !== null && ev.current_experience_fit !== undefined) ? `${ev.current_experience_fit}/100` : `—`;
    llmTransFit.textContent = (ev.transferable_capability_fit !== null && ev.transferable_capability_fit !== undefined) ? `${ev.transferable_capability_fit}/100` : `—`;
    llmSenFit.textContent = (ev.seniority_fit !== null && ev.seniority_fit !== undefined) ? `${ev.seniority_fit}/100` : `—`;
    llmProbObtain.textContent = (ev.probability_of_obtaining !== null && ev.probability_of_obtaining !== undefined) ? `${ev.probability_of_obtaining}%` : `—`;
    
    if (ev.transition_difficulty || ev.career_upside) {
      llmDiffUpside.textContent = `${ev.transition_difficulty || "—"} / ${ev.career_upside || "—"}`;
    } else {
      llmDiffUpside.textContent = "—";
    }

    const strengths = ev.key_strengths || ev.strengths || [];
    llmStrengthsList.innerHTML = strengths.length > 0 
      ? strengths.map(s => `<li>${escapeHtml(s)}</li>`).join("") 
      : `<li>No specific strengths highlighted</li>`;

    const gaps = ev.missing_critical_skills || ev.gaps || [];
    llmGapsList.innerHTML = gaps.length > 0 
      ? gaps.map(g => `<li>${escapeHtml(g)}</li>`).join("") 
      : `<li>No critical capability gaps identified</li>`;

    llmReasoning.textContent = ev.reasoning && ev.reasoning !== "UNKNOWN" ? ev.reasoning : (ev.evidence || "No detailed reasoning text provided.");
  } else if (isGateRejected) {
    const reasons = job.gate_failure_reasons || [];
    const passed = job.gate_passed_checks || [];

    llmRecBadge.textContent = "GATE REJECTED — PRE-LLM";
    llmRecBadge.style.background = "rgba(244, 63, 94, 0.15)";
    llmRecBadge.style.color = "var(--accent-rose)";
    llmRecBadge.style.borderColor = "rgba(244, 63, 94, 0.3)";
    llmScorePill.textContent = "SCORE: — (GATE REJECTED)";
    llmRoleFit.textContent = "—";
    llmExpFit.textContent = "—";
    llmTransFit.textContent = "—";
    llmSenFit.textContent = "—";
    llmProbObtain.textContent = "—";
    llmDiffUpside.textContent = "—";

    llmStrengthsList.innerHTML = passed.length > 0
      ? passed.map(p => `<li>${escapeHtml(p)}</li>`).join("")
      : `<li>No LLM evaluation performed (filtered at candidate constraint gate)</li>`;

    llmGapsList.innerHTML = reasons.length > 0
      ? reasons.map(r => `<li style="color: var(--accent-rose);">${escapeHtml(r)}</li>`).join("")
      : `<li>Candidate constraint gate exclusion</li>`;

    llmReasoning.textContent = reasons.length > 0
      ? `Opportunity was excluded by candidate constraint gate before LLM evaluation:\n• ` + reasons.join("\n• ")
      : "Opportunity excluded by candidate constraint gate.";
  } else if (isFailed) {
    llmRecBadge.textContent = "EVALUATION FAILED";
    llmRecBadge.style.background = "rgba(239, 68, 68, 0.15)";
    llmRecBadge.style.color = "#ef4444";
    llmRecBadge.style.borderColor = "rgba(239, 68, 68, 0.3)";
    llmScorePill.textContent = "SCORE: — (FAILED)";
    llmRoleFit.textContent = "—";
    llmExpFit.textContent = "—";
    llmTransFit.textContent = "—";
    llmSenFit.textContent = "—";
    llmProbObtain.textContent = "—";
    llmDiffUpside.textContent = "—";
    llmStrengthsList.innerHTML = `<li>Evaluation execution failed</li>`;
    llmGapsList.innerHTML = `<li>Evaluation execution failed</li>`;
    llmReasoning.textContent = "LLM evaluation execution failed or was interrupted.";
  } else {
    llmRecBadge.textContent = "PENDING EVALUATION";
    llmRecBadge.style.background = "rgba(245, 158, 11, 0.15)";
    llmRecBadge.style.color = "var(--accent-amber)";
    llmRecBadge.style.borderColor = "rgba(245, 158, 11, 0.3)";
    llmScorePill.textContent = "SCORE: —";
    llmRoleFit.textContent = "—";
    llmExpFit.textContent = "—";
    llmTransFit.textContent = "—";
    llmSenFit.textContent = "—";
    llmProbObtain.textContent = "—";
    llmDiffUpside.textContent = "—";
    llmStrengthsList.innerHTML = `<li>Pending LLM evaluation</li>`;
    llmGapsList.innerHTML = `<li>Pending LLM evaluation</li>`;
    llmReasoning.textContent = "LLM evaluation for this opportunity is pending.";
  }

  // Description
  jobDescription.textContent = job.description || "No full job description provided by source.";

  // Decision Form
  const decision = humanDecisions[job.job_id];
  if (decision) {
    decisionStatus.textContent = `REVIEWED — ${decision.verdict}`;
    decisionStatus.style.color = "var(--accent-emerald)";
    selectVerdict(decision.verdict);
    selectCounterfactual(decision.counterfactual);
    selectPriority(decision.priority);
    selectOpportunityStatus(decision.opportunity_status || "UNKNOWN");
    selectApplicationStatus(decision.application_status || "NOT_APPLIED");
    humanNotes.value = decision.notes || "";
  } else {
    decisionStatus.textContent = "UNREVIEWED";
    decisionStatus.style.color = "var(--text-muted)";
    resetDecisionForm();
  }

  // Update progress subtext
  queueProgress.textContent = `(Item ${currentJobIndex + 1} of ${currentFilteredJobs.length})`;
  highlightActiveNavigatorItem();

  // Load Application Lifecycle & Evidence Timeline
  loadOpportunityTimeline(job.job_id);
}

function selectVerdict(verdict) {
  verdictButtons.forEach(btn => {
    if (btn.getAttribute("data-verdict") === verdict) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });

  if (verdict) {
    decisionStatus.textContent = `SELECTED — ${verdict}`;
    if (verdict === "RELEVANT") {
      decisionStatus.style.color = "var(--accent-emerald)";
      decisionStatus.style.borderColor = "rgba(16, 185, 129, 0.4)";
      decisionStatus.style.background = "rgba(16, 185, 129, 0.15)";
    } else if (verdict === "ADJACENT") {
      decisionStatus.style.color = "var(--accent-cyan)";
      decisionStatus.style.borderColor = "rgba(6, 182, 212, 0.4)";
      decisionStatus.style.background = "rgba(6, 182, 212, 0.15)";
    } else if (verdict === "WEAK") {
      decisionStatus.style.color = "var(--accent-amber)";
      decisionStatus.style.borderColor = "rgba(245, 158, 11, 0.4)";
      decisionStatus.style.background = "rgba(245, 158, 11, 0.15)";
    } else if (verdict === "IRRELEVANT") {
      decisionStatus.style.color = "var(--accent-rose)";
      decisionStatus.style.borderColor = "rgba(244, 63, 94, 0.4)";
      decisionStatus.style.background = "rgba(244, 63, 94, 0.15)";
    }
  }
}

function selectCounterfactual(cf) {
  cfButtons.forEach(btn => {
    if (btn.getAttribute("data-cf") === cf) {
      btn.style.borderColor = "var(--accent-blue)";
      btn.style.background = "rgba(56, 189, 248, 0.2)";
      btn.style.color = "var(--text-primary)";
    } else {
      btn.style.borderColor = "var(--border-color)";
      btn.style.background = "var(--bg-card)";
      btn.style.color = "var(--text-secondary)";
    }
  });
}

function selectPriority(prio) {
  priorityButtons.forEach(btn => {
    if (btn.getAttribute("data-priority") === prio) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });
}

function selectOpportunityStatus(status) {
  const norm = (status || "UNKNOWN").toUpperCase();
  oppStatusButtons.forEach(btn => {
    if (btn.getAttribute("data-opp") === norm) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });
}

function selectApplicationStatus(status) {
  const norm = (status || "NOT_APPLIED").toUpperCase();
  appStatusButtons.forEach(btn => {
    if (btn.getAttribute("data-app") === norm) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });
}

function resetDecisionForm() {
  verdictButtons.forEach(btn => btn.classList.remove("selected"));
  cfButtons.forEach(btn => {
    btn.style.borderColor = "var(--border-color)";
    btn.style.background = "var(--bg-card)";
    btn.style.color = "var(--text-secondary)";
  });
  priorityButtons.forEach(btn => btn.classList.remove("selected"));
  selectOpportunityStatus("UNKNOWN");
  selectApplicationStatus("NOT_APPLIED");
  humanNotes.value = "";
  decisionStatus.textContent = "UNREVIEWED";
  decisionStatus.style.color = "var(--text-muted)";
  decisionStatus.style.borderColor = "var(--border-color)";
  decisionStatus.style.background = "var(--bg-subtle)";
}

async function saveDecisionAndNext() {
  if (currentFilteredJobs.length === 0) return;
  const job = currentFilteredJobs[currentJobIndex];

  const selectedVerdictBtn = document.querySelector(".verdict-btn.selected");
  if (!selectedVerdictBtn) {
    alert("Please select a Discovery Verdict (Relevant, Adjacent, Weak, Irrelevant)");
    return;
  }

  const verdict = selectedVerdictBtn.getAttribute("data-verdict");
  
  let cfValue = "";
  cfButtons.forEach(btn => {
    if (btn.style.borderColor.includes("var(--accent-blue)") || btn.style.borderColor.includes("56, 189, 248")) {
      cfValue = btn.getAttribute("data-cf");
    }
  });

  const selectedPriorityBtn = document.querySelector(".priority-btn.selected");
  const priorityValue = selectedPriorityBtn ? selectedPriorityBtn.getAttribute("data-priority") : "";

  const selectedOppBtn = document.querySelector(".opp-status-btn.selected");
  const oppValue = selectedOppBtn ? selectedOppBtn.getAttribute("data-opp") : "UNKNOWN";

  const selectedAppBtn = document.querySelector(".app-status-btn.selected");
  const appValue = selectedAppBtn ? selectedAppBtn.getAttribute("data-app") : "NOT_APPLIED";

  const payload = {
    job_id: job.job_id,
    verdict: verdict,
    counterfactual: cfValue || "UNSURE",
    priority: priorityValue || "MEDIUM",
    opportunity_status: oppValue || "UNKNOWN",
    application_status: appValue || "NOT_APPLIED",
    notes: humanNotes.value.trim(),
    opportunity_type: job.provenance ? job.provenance.opportunity_type : "",
    search_query: job.provenance ? job.provenance.search_query : "",
    source: job.source || "",
  };

  try {
    const res = await fetch("/api/discovery/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = await res.json();

    humanDecisions[job.job_id] = result.decision;
    updateBadges();
    renderNavigator();

    // Advance to next
    if (currentJobIndex < currentFilteredJobs.length - 1) {
      currentJobIndex++;
      renderCurrentJob();
    } else {
      renderCurrentJob();
    }
  } catch (err) {
    alert(`Error saving decision: ${err.message}`);
  }
}

function setupEventListeners() {
  // Opportunity Type filters
  typeNav.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      typeNav.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filterState.type = btn.getAttribute("data-type");
      applyFilters();
    });
  });

  // LLM Recommendation filter
  llmRecSelect.addEventListener("change", e => {
    filterState.llmRec = e.target.value;
    applyFilters();
  });

  // Human Review filter
  humanReviewSelect.addEventListener("change", e => {
    filterState.humanReview = e.target.value;
    applyFilters();
  });

  // Opportunity Status filter
  oppStatusSelect.addEventListener("change", e => {
    filterState.oppStatus = e.target.value;
    applyFilters();
  });

  // Application Status filter
  appStatusSelect.addEventListener("change", e => {
    filterState.appStatus = e.target.value;
    applyFilters();
  });

  // Intent dropdown
  intentSelect.addEventListener("change", e => {
    filterState.intent = e.target.value;
    applyFilters();
  });

  // Source dropdown
  sourceSelect.addEventListener("change", e => {
    filterState.source = e.target.value;
    applyFilters();
  });

  // Quick Search input
  searchInput.addEventListener("input", e => {
    filterState.searchQuery = e.target.value;
    applyFilters();
  });

  // Reset filters
  resetFiltersBtn.addEventListener("click", () => {
    filterState.type = "ALL";
    filterState.llmRec = "ALL";
    filterState.humanReview = "ALL";
    filterState.oppStatus = "ALL";
    filterState.appStatus = "ALL";
    filterState.intent = "ALL";
    filterState.source = "ALL";
    filterState.searchQuery = "";

    typeNav.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    const allBtn = typeNav.querySelector('[data-type="ALL"]');
    if (allBtn) allBtn.classList.add("active");

    llmRecSelect.value = "ALL";
    humanReviewSelect.value = "ALL";
    oppStatusSelect.value = "ALL";
    appStatusSelect.value = "ALL";
    intentSelect.value = "ALL";
    sourceSelect.value = "ALL";
    searchInput.value = "";

    applyFilters();
  });

  // Verdict buttons
  verdictButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      selectVerdict(btn.getAttribute("data-verdict"));
    });
  });

  // Counterfactual buttons
  cfButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      selectCounterfactual(btn.getAttribute("data-cf"));
    });
  });

  // Priority buttons
  priorityButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      selectPriority(btn.getAttribute("data-priority"));
    });
  });

  // Opportunity Status buttons
  oppStatusButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      selectOpportunityStatus(btn.getAttribute("data-opp"));
    });
  });

  // Application Status buttons
  appStatusButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      selectApplicationStatus(btn.getAttribute("data-app"));
    });
  });

  // Action buttons
  saveNextBtn.addEventListener("click", saveDecisionAndNext);

  prevBtn.addEventListener("click", () => {
    if (currentJobIndex > 0) {
      currentJobIndex--;
      renderCurrentJob();
    }
  });

  nextBtn.addEventListener("click", () => {
    if (currentJobIndex < currentFilteredJobs.length - 1) {
      currentJobIndex++;
      renderCurrentJob();
    }
  });

  // Summary modal
  summaryBtn.addEventListener("click", openSummary);
  closeSummaryModal.addEventListener("click", () => {
    summaryModal.style.display = "none";
  });
  summaryModal.addEventListener("click", e => {
    if (e.target === summaryModal) summaryModal.style.display = "none";
  });

  // Keyboard Shortcuts
  document.addEventListener("keydown", e => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT" || e.target.tagName === "SELECT") {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        saveDecisionAndNext();
      }
      return;
    }

    // Escape to close modals
    if (e.key === "Escape") {
      if (summaryModal.style.display !== "none") {
        summaryModal.style.display = "none";
      }
    }

    // Verdicts: 1, 2, 3, 4
    if (e.key === "1") { e.preventDefault(); selectVerdict("RELEVANT"); }
    if (e.key === "2") { e.preventDefault(); selectVerdict("ADJACENT"); }
    if (e.key === "3") { e.preventDefault(); selectVerdict("WEAK"); }
    if (e.key === "4") { e.preventDefault(); selectVerdict("IRRELEVANT"); }

    // Counterfactuals: Y, P, N, U
    if (e.key.toLowerCase() === "y") { e.preventDefault(); selectCounterfactual("YES"); }
    if (e.key.toLowerCase() === "p") { e.preventDefault(); selectCounterfactual("PROBABLY"); }
    if (e.key.toLowerCase() === "n") { e.preventDefault(); selectCounterfactual("NO"); }
    if (e.key.toLowerCase() === "u") { e.preventDefault(); selectCounterfactual("UNSURE"); }

    // Priorities: H, M, L
    if (e.key.toLowerCase() === "h") { e.preventDefault(); selectPriority("HIGH"); }
    if (e.key.toLowerCase() === "m") { e.preventDefault(); selectPriority("MEDIUM"); }
    if (e.key.toLowerCase() === "l") { e.preventDefault(); selectPriority("LOW"); }

    // Navigation & Submission
    if (e.key === "Enter") { e.preventDefault(); saveDecisionAndNext(); }
    if (e.key === "ArrowLeft" || e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (currentJobIndex > 0) { currentJobIndex--; renderCurrentJob(); }
    }
    if (e.key === "ArrowRight" || e.key.toLowerCase() === "j") {
      e.preventDefault();
      if (currentJobIndex < currentFilteredJobs.length - 1) { currentJobIndex++; renderCurrentJob(); }
    }
  });
}

async function openSummary() {
  try {
    const res = await fetch("/api/discovery/summary");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    document.getElementById("modalTotalDiscovered").textContent = data.total_discovered;
    document.getElementById("modalTotalReviewed").textContent = data.total_reviewed;
    document.getElementById("modalRelevant").textContent = data.verdicts.RELEVANT;
    document.getElementById("modalAdjacent").textContent = data.verdicts.ADJACENT;
    document.getElementById("modalWeakIrrelevant").textContent = (data.verdicts.WEAK + data.verdicts.IRRELEVANT);

    // Populate Type Breakdown
    const typeBody = document.getElementById("typeBreakdownBody");
    typeBody.innerHTML = "";
    Object.entries(data.by_opportunity_type).forEach(([typeKey, stats]) => {
      const tr = document.createElement("tr");
      tr.style.borderBottom = "1px solid var(--border-color)";
      const discoveryYield = stats.cf_NO + stats.cf_UNSURE;
      tr.innerHTML = `
        <td style="padding: 0.6rem 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--accent-blue);">${typeKey}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.total}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.reviewed}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-emerald); font-weight: 600;">${stats.RELEVANT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-cyan); font-weight: 600;">${stats.ADJACENT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-rose);">${stats.WEAK + stats.IRRELEVANT}</td>
        <td style="padding: 0.6rem 0.75rem; font-family: var(--font-mono);">${discoveryYield} (${stats.reviewed ? Math.round(discoveryYield / stats.reviewed * 100) : 0}%)</td>
      `;
      typeBody.appendChild(tr);
    });

    // Populate Intent Breakdown
    const intentBody = document.getElementById("intentBreakdownBody");
    intentBody.innerHTML = "";
    Object.entries(data.by_search_intent).forEach(([intentKey, stats]) => {
      const tr = document.createElement("tr");
      tr.style.borderBottom = "1px solid var(--border-color)";
      tr.innerHTML = `
        <td style="padding: 0.6rem 0.75rem; font-family: var(--font-mono); color: var(--text-primary);">${escapeHtml(intentKey)}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.total}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.reviewed}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-emerald); font-weight: 600;">${stats.RELEVANT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-cyan); font-weight: 600;">${stats.ADJACENT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-rose);">${stats.WEAK + stats.IRRELEVANT}</td>
      `;
      intentBody.appendChild(tr);
    });

    // Populate Source Breakdown
    const srcBody = document.getElementById("sourceBreakdownBody");
    srcBody.innerHTML = "";
    Object.entries(data.by_source).forEach(([srcKey, stats]) => {
      const tr = document.createElement("tr");
      tr.style.borderBottom = "1px solid var(--border-color)";
      tr.innerHTML = `
        <td style="padding: 0.6rem 0.75rem; font-weight: 600; text-transform: uppercase;">${srcKey}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.total}</td>
        <td style="padding: 0.6rem 0.75rem;">${stats.reviewed}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-emerald); font-weight: 600;">${stats.RELEVANT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-cyan); font-weight: 600;">${stats.ADJACENT}</td>
        <td style="padding: 0.6rem 0.75rem; color: var(--accent-rose);">${stats.WEAK + stats.IRRELEVANT}</td>
      `;
      srcBody.appendChild(tr);
    });

    summaryModal.style.display = "flex";
  } catch (err) {
    alert(`Error loading summary: ${err.message}`);
  }
}

function formatSalary(job) {
  if (!job) return "Salary Not Listed";

  if (job.salary_min != null || job.salary_max != null) {
    try {
      const min = job.salary_min != null ? `₹${Number(job.salary_min).toLocaleString('en-IN')}` : "";
      const max = job.salary_max != null ? `₹${Number(job.salary_max).toLocaleString('en-IN')}` : "";
      const interval = job.salary_interval ? ` ${job.salary_interval}` : "";
      if (min && max) {
        return `${min} - ${max}${interval}`;
      } else if (min) {
        return `From ${min}${interval}`;
      } else if (max) {
        return `Up to ${max}${interval}`;
      }
    } catch (e) {
      // Fallback
    }
  }

  if (job.salary_raw || job.salary) {
    return String(job.salary_raw || job.salary).trim();
  }

  const desc = job.description || "";
  if (desc) {
    const cleaned = desc.replace(/\\\./g, ".").replace(/\\-/g, "-").replace(/\\_/g, "_").replace(/\\\*/g, "*");

    // 1. CTC / Salary headers e.g. **CTC:** Up to 10 LPA or CTC: 12-18 LPA
    const ctcMatch = cleaned.match(/(?:\*\*|\b)(?:CTC|Salary|Package|Pay|Compensation)(?:\*\*|\b)?\s*[:\-–]\s*([^\n\r*#_]+)/i);
    if (ctcMatch && ctcMatch[1]) {
      const val = ctcMatch[1].trim().replace(/^[*_`]+|[*_`]+$/g, "");
      if (/(?:LPA|lpa|INR|₹|Rs\.?|lakh|crore|\d+\s*(?:a|per)\s*(?:year|annum|month|yr|mo)|\d{5,})/i.test(val)) {
        return val;
      }
    }

    // 2. Explicit Rupee amount patterns e.g. ₹10,00,000 - ₹20,00,000 a year
    const rupeeMatch = cleaned.match(/(₹\s*[\d,]+(?:\.\d{2})?(?:\s*-\s*₹?\s*[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per)\s*(?:year|month|annum|yr|mo))?)/i);
    if (rupeeMatch && rupeeMatch[1]) {
      return rupeeMatch[1].trim();
    }

    // 3. LPA standalone pattern e.g. 10-15 LPA, Up to 10 LPA
    const lpaMatch = cleaned.match(/((?:Up to\s+)?\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*LPA)/i);
    if (lpaMatch && lpaMatch[1]) {
      return lpaMatch[1].trim();
    }
  }

  return "Salary Not Listed";
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// =========================================================
// Application Lifecycle & Gmail Timeline Functions
// =========================================================

async function loadOpportunityTimeline(jobId) {
  const listEl = document.getElementById("timelineList");
  const badgeEl = document.getElementById("timelineStatusBadge");
  if (!listEl || !badgeEl) return;

  try {
    const res = await fetch(`/api/timeline?opportunity_id=${encodeURIComponent(jobId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const timeline = data.timeline || [];

    badgeEl.textContent = `${timeline.length} Record${timeline.length === 1 ? "" : "s"}`;

    if (timeline.length === 0) {
      listEl.innerHTML = `<div style="font-size: 0.8125rem; color: var(--text-muted); font-style: italic; padding: 0.5rem 0;">No Gmail events or status transitions recorded yet for this opportunity.</div>`;
      return;
    }

    listEl.innerHTML = timeline.map(item => {
      const type = item.type || "EVENT";
      const isStatusChange = type === "APPLICATION_STATUS_CHANGE";
      
      let badgeBg = "rgba(56, 189, 248, 0.15)";
      let badgeColor = "var(--accent-blue)";
      let badgeLabel = type.replace(/_/g, " ");

      if (type.includes("OFFER")) {
        badgeBg = "rgba(245, 158, 11, 0.2)";
        badgeColor = "var(--accent-amber)";
      } else if (type.includes("INTERVIEW")) {
        badgeBg = "rgba(16, 185, 129, 0.2)";
        badgeColor = "var(--accent-emerald)";
      } else if (type.includes("REJECTION")) {
        badgeBg = "rgba(244, 63, 94, 0.2)";
        badgeColor = "var(--accent-rose)";
      } else if (type.includes("CONFIRMATION")) {
        badgeBg = "rgba(139, 92, 246, 0.2)";
        badgeColor = "var(--accent-violet)";
      }

      const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleString() : "Unknown Time";

      return `
        <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 6px; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.35rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px; background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor};">
                ${badgeLabel}
              </span>
              ${item.transition ? `<span style="font-size: 0.75rem; font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">${escapeHtml(item.transition)}</span>` : ""}
            </div>
            <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${dateStr}</span>
          </div>
          ${item.subject ? `<div style="font-size: 0.8125rem; font-weight: 600; color: var(--text-primary); margin-top: 0.15rem;">Subject: "${escapeHtml(item.subject)}"</div>` : ""}
          ${item.sender ? `<div style="font-size: 0.72rem; color: var(--text-secondary);">From: <span style="font-family: var(--font-mono);">${escapeHtml(item.sender)}</span></div>` : ""}
          ${item.reason ? `<div style="font-size: 0.75rem; color: var(--text-muted); font-style: italic; background: rgba(0,0,0,0.2); padding: 0.3rem 0.5rem; border-radius: 4px; margin-top: 0.2rem;">${escapeHtml(item.reason)}</div>` : ""}
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Failed to load timeline:", err);
    listEl.innerHTML = `<div style="font-size: 0.8125rem; color: var(--accent-rose);">Error loading timeline: ${escapeHtml(err.message)}</div>`;
  }
}

// =========================================================
// Gmail Synchronization & Review Modal Integration
// =========================================================

function initGmailIntegration() {
  const gmailSyncBtn = document.getElementById("gmailSyncBtn");
  const gmailModal = document.getElementById("gmailModal");
  const closeGmailModalBtn = document.getElementById("closeGmailModalBtn");
  const connectGmailBtn = document.getElementById("connectGmailBtn");
  const disconnectGmailBtn = document.getElementById("disconnectGmailBtn");
  const runDryRunBtn = document.getElementById("runDryRunBtn");
  const applyChangesBtn = document.getElementById("applyChangesBtn");
  const syncAdapterSelect = document.getElementById("syncAdapterSelect");
  const syncAfterDate = document.getElementById("syncAfterDate");
  const dryRunPreviewContainer = document.getElementById("dryRunPreviewContainer");
  const dryRunOutput = document.getElementById("dryRunOutput");
  const pendingEventsList = document.getElementById("pendingEventsList");
  const pendingEventsBadge = document.getElementById("pendingEventsBadge");

  // Check URL query parameters for OAuth callback feedback
  const params = new URLSearchParams(window.location.search);
  if (params.get("gmail_status") === "connected") {
    alert(`Gmail connected successfully! Account: ${params.get("email") || "Active Account"}`);
    window.history.replaceState({}, document.title, window.location.pathname);
  } else if (params.get("gmail_error")) {
    alert(`Gmail connection error: ${params.get("gmail_error")}`);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  // Open modal
  gmailSyncBtn?.addEventListener("click", () => {
    if (gmailModal) gmailModal.style.display = "flex";
    refreshGmailStatus();
    loadPendingEvents();
  });

  // Close modal
  closeGmailModalBtn?.addEventListener("click", () => {
    if (gmailModal) gmailModal.style.display = "none";
  });

  // Connect Gmail Button (OAuth)
  connectGmailBtn?.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/gmail/auth-url");
      const data = await res.json();
      if (!res.ok) {
        if (data.is_config_error) {
          alert(`Google OAuth is not configured yet:\n\n${data.error}\n\nHint: ${data.hint}\n\nYou can still test using the Deterministic Mock Adapter!`);
        } else {
          alert(`OAuth error: ${data.error || "Failed to generate auth URL"}`);
        }
        return;
      }
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      alert(`Error initiating Google OAuth: ${err.message}`);
    }
  });

  // Disconnect Gmail Button
  disconnectGmailBtn?.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to disconnect your Gmail account from Career OS?")) return;
    try {
      const res = await fetch("/api/gmail/disconnect", { method: "POST" });
      if (res.ok) {
        alert("Gmail account disconnected.");
        refreshGmailStatus();
      }
    } catch (err) {
      alert(`Error disconnecting: ${err.message}`);
    }
  });

  // Run Dry-Run Preview
  runDryRunBtn?.addEventListener("click", async () => {
    const adapterType = syncAdapterSelect?.value || "auto";
    const afterDate = syncAfterDate?.value || null;

    runDryRunBtn.disabled = true;
    runDryRunBtn.innerHTML = "Scanning...";

    try {
      const res = await fetch("/api/gmail/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dry_run: true,
          adapter_type: adapterType,
          after_date: afterDate,
          max_results: 50
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      if (dryRunPreviewContainer && dryRunOutput) {
        dryRunPreviewContainer.style.display = "block";
        dryRunOutput.textContent = data.formatted_preview || JSON.stringify(data.report, null, 2);
      }

      loadPendingEvents();
    } catch (err) {
      alert(`Error during dry-run preview: ${err.message}`);
    } finally {
      runDryRunBtn.disabled = false;
      runDryRunBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Run Dry-Run Preview`;
    }
  });

  // Approve & Apply State Changes (Live Mutation)
  applyChangesBtn?.addEventListener("click", async () => {
    const adapterType = syncAdapterSelect?.value || "auto";
    const afterDate = syncAfterDate?.value || null;

    if (!confirm("Are you sure you want to apply these proposed state transitions to your Career OS database?\n\nThis will mutate application statuses and record auditable career events.")) {
      return;
    }

    applyChangesBtn.disabled = true;
    applyChangesBtn.innerHTML = "Applying...";

    try {
      const res = await fetch("/api/gmail/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dry_run: false, // Explicit approved live mutation!
          adapter_type: adapterType,
          after_date: afterDate,
          max_results: 50
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      if (dryRunOutput) {
        dryRunOutput.textContent = data.formatted_preview || "Live mutations applied successfully.";
      }

      alert(`Sync applied successfully! ${data.report?.mutations_applied || 0} transitions recorded.`);
      
      // Refresh current job view and timeline
      await fetchDiscoveryData();
      if (currentFilteredJobs.length > 0 && currentFilteredJobs[currentJobIndex]) {
        loadOpportunityTimeline(currentFilteredJobs[currentJobIndex].job_id);
      }
      loadPendingEvents();
    } catch (err) {
      alert(`Error applying changes: ${err.message}`);
    } finally {
      applyChangesBtn.disabled = false;
      applyChangesBtn.innerHTML = "Approve & Apply State Changes";
    }
  });

  async function refreshGmailStatus() {
    const statusText = document.getElementById("gmailStatusText");
    const checkpointText = document.getElementById("gmailCheckpointText");
    if (!statusText) return;

    try {
      const res = await fetch("/api/gmail/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.connected) {
        statusText.innerHTML = `<span style="color: var(--accent-emerald);">● Connected: <strong>${escapeHtml(data.account_email)}</strong></span>`;
        if (connectGmailBtn) connectGmailBtn.style.display = "none";
        if (disconnectGmailBtn) disconnectGmailBtn.style.display = "inline-flex";
      } else {
        statusText.innerHTML = `<span style="color: var(--text-muted);">○ Not Connected (Using Deterministic Mock Adapter)</span>`;
        if (connectGmailBtn) connectGmailBtn.style.display = "inline-flex";
        if (disconnectGmailBtn) disconnectGmailBtn.style.display = "none";
      }

      if (checkpointText) {
        if (data.checkpoint && data.checkpoint.last_sync_timestamp) {
          checkpointText.textContent = `Last Synced: ${new Date(data.checkpoint.last_sync_timestamp).toLocaleString()} • Processed: ${data.checkpoint.messages_processed || 0} msgs`;
        } else {
          checkpointText.textContent = `No live sync checkpoint recorded yet.`;
        }
      }
    } catch (err) {
      console.error("Failed to load Gmail status:", err);
      statusText.textContent = "Unable to fetch status";
    }
  }

  async function loadPendingEvents() {
    if (!pendingEventsList || !pendingEventsBadge) return;

    try {
      const res = await fetch("/api/events?status=PENDING_CONFIRMATION");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const events = data.events || [];

      pendingEventsBadge.textContent = `${events.length} Pending`;

      if (events.length === 0) {
        pendingEventsList.innerHTML = `<div style="font-size: 0.8125rem; color: var(--text-muted); font-style: italic;">No pending or ambiguous events requiring human confirmation.</div>`;
        return;
      }

      pendingEventsList.innerHTML = events.map(ev => {
        return `
          <div style="background: var(--bg-card); border: 1px solid var(--accent-amber); border-radius: 6px; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.35rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.4rem; border-radius: 3px; background: rgba(245, 158, 11, 0.2); color: var(--accent-amber);">
                ${escapeHtml(ev.event_type)} (Ambiguous / Low Confidence)
              </span>
              <span style="font-size: 0.7rem; color: var(--text-muted);">${ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleDateString() : ""}</span>
            </div>
            <div style="font-size: 0.8125rem; font-weight: 600; color: var(--text-primary);">"${escapeHtml(ev.source_subject || "No Subject")}"</div>
            <div style="font-size: 0.72rem; color: var(--text-secondary);">From: <span style="font-family: var(--font-mono);">${escapeHtml(ev.source_sender || "")}</span></div>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; align-items: center;">
              <input type="text" placeholder="Opportunity ID (e.g. disc_0001)" id="opp_input_${ev.id}" value="${ev.opportunity_id || ""}" style="background: var(--bg-subtle); color: var(--text-primary); border: 1px solid var(--border-color); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; flex: 1;">
              <button class="action-btn primary" onclick="decideEvent('${ev.id}', 'confirm')" style="font-size: 0.75rem; padding: 0.25rem 0.6rem; background: #10b981; border-color: #10b981;">Confirm Match</button>
              <button class="action-btn secondary" onclick="decideEvent('${ev.id}', 'dismiss')" style="font-size: 0.75rem; padding: 0.25rem 0.6rem; color: var(--accent-rose);">Dismiss</button>
            </div>
          </div>
        `;
      }).join("");

    } catch (err) {
      console.error("Failed to load pending events:", err);
    }
  }

  // Global helper for event triage buttons
  window.decideEvent = async function(eventId, action) {
    const oppInput = document.getElementById(`opp_input_${eventId}`);
    const oppId = oppInput ? oppInput.value.trim() : "";

    if (action === "confirm" && !oppId) {
      alert("Please provide the Opportunity ID to link this event to.");
      return;
    }

    try {
      const res = await fetch("/api/events/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_id: eventId,
          opportunity_id: oppId,
          action: action,
          notes: "Manually resolved via triage modal"
        })
      });

      if (res.ok) {
        loadPendingEvents();
        if (currentFilteredJobs[currentJobIndex]) {
          loadOpportunityTimeline(currentFilteredJobs[currentJobIndex].job_id);
        }
      } else {
        const err = await res.json();
        alert(`Error: ${err.error}`);
      }
    } catch (e) {
      alert(`Error updating event: ${e.message}`);
    }
  };
}


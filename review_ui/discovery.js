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
    if (job.gate_failed) {
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); font-weight: 700; padding: 0.1rem 0.35rem; border-radius: 3px; background: rgba(244, 63, 94, 0.15); color: var(--accent-rose); border: 1px solid rgba(244, 63, 94, 0.3);">GATE REJ [0]</span>`;
    } else if (job.llm_evaluation) {
      const rec = job.llm_evaluation.recommendation || "Skip";
      const score = job.llm_evaluation.overall_score || 0;
      let badgeStyle = "background: rgba(148, 163, 184, 0.15); color: var(--text-secondary); border: 1px solid rgba(148, 163, 184, 0.3);";
      if (rec === "Strong Apply" || rec === "Apply") {
        badgeStyle = "background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.4);";
      } else if (rec === "Consider") {
        badgeStyle = "background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.4);";
      } else if (rec === "Long Shot") {
        badgeStyle = "background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); font-weight: 600; border: 1px solid rgba(245, 158, 11, 0.4);";
      }
      llmBadgeHtml = `<span style="font-size: 0.65rem; font-family: var(--font-mono); padding: 0.1rem 0.35rem; border-radius: 3px; ${badgeStyle}">${rec.toUpperCase()} [${score}]</span>`;
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
  if (currentFilteredJobs.length === 0) {
    jobTitle.textContent = "No opportunities in current filter view";
    jobCompany.textContent = "Adjust filter criteria in the toolbar above.";
    jobLocation.textContent = "—";
    jobSalary.textContent = "—";
    provQuery.textContent = "—";
    provHypothesis.textContent = "—";
    provSourceTime.textContent = "—";
    jobDescription.textContent = "No job selected.";
    decisionStatus.textContent = "N/A";
    resetDecisionForm();
    return;
  }

  const job = currentFilteredJobs[currentJobIndex];
  const otype = (job.provenance && job.provenance.opportunity_type || "direct").toUpperCase();
  const prov = job.provenance || {};

  jobIdTag.textContent = job.job_id;
  jobTypeTag.textContent = otype;
  jobSourceTag.textContent = (job.source || "UNKNOWN").toUpperCase();
  jobLocation.textContent = job.location || "India";
  
  if (job.salary_min || job.salary_max) {
    const min = job.salary_min ? `₹${Number(job.salary_min).toLocaleString()}` : "";
    const max = job.salary_max ? `₹${Number(job.salary_max).toLocaleString()}` : "";
    jobSalary.textContent = `${min} - ${max} ${job.salary_interval || ""}`.trim();
  } else {
    jobSalary.textContent = "Salary Not Listed";
  }

  jobTitle.textContent = job.title;
  jobCompany.textContent = job.company;

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

  // LLM Evaluation Context Display
  if (job.gate_failed) {
    llmRecBadge.textContent = "GATE REJECTED";
    llmRecBadge.style.background = "rgba(244, 63, 94, 0.2)";
    llmRecBadge.style.color = "var(--accent-rose)";
    llmRecBadge.style.borderColor = "var(--accent-rose)";
    llmScorePill.textContent = "SCORE: 0/100";
    llmRoleFit.textContent = "0/100";
    llmExpFit.textContent = "0/100";
    llmTransFit.textContent = "0/100";
    llmSenFit.textContent = "0/100";
    llmProbObtain.textContent = "0%";
    llmDiffUpside.textContent = "Rejected by Gate";
    llmStrengthsList.innerHTML = `<li>No candidate fit assessment performed</li>`;
    llmGapsList.innerHTML = (job.gate_failure_reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join("") || `<li>Explicit constraint gate failed</li>`;
    llmReasoning.textContent = "This opportunity was excluded by explicit employment-type/recency constraint gates before LLM evaluation.";
  } else if (job.llm_evaluation) {
    const ev = job.llm_evaluation;
    const rec = ev.recommendation || "Skip";
    const score = ev.overall_score !== undefined ? ev.overall_score : 0;

    llmRecBadge.textContent = rec.toUpperCase();
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

    llmScorePill.textContent = `SCORE: ${score}/100`;
    llmRoleFit.textContent = `${ev.role_fit || 0}/100`;
    llmExpFit.textContent = `${ev.current_experience_fit || 0}/100`;
    llmTransFit.textContent = `${ev.transferable_capability_fit || 0}/100`;
    llmSenFit.textContent = `${ev.seniority_fit || 0}/100`;
    llmProbObtain.textContent = `${ev.probability_of_obtaining || 0}%`;
    llmDiffUpside.textContent = `${ev.transition_difficulty || "medium"} / ${ev.career_upside || "unknown"}`;

    const strengths = ev.key_strengths || [];
    llmStrengthsList.innerHTML = strengths.length > 0 
      ? strengths.map(s => `<li>${escapeHtml(s)}</li>`).join("") 
      : `<li>No specific strengths highlighted</li>`;

    const gaps = ev.missing_critical_skills || [];
    llmGapsList.innerHTML = gaps.length > 0 
      ? gaps.map(g => `<li>${escapeHtml(g)}</li>`).join("") 
      : `<li>No critical capability gaps identified</li>`;

    llmReasoning.textContent = ev.reasoning && ev.reasoning !== "UNKNOWN" ? ev.reasoning : (ev.evidence || "No detailed reasoning text provided.");
  } else {
    llmRecBadge.textContent = "NOT EVALUATED";
    llmRecBadge.style.background = "var(--bg-hover)";
    llmRecBadge.style.color = "var(--text-muted)";
    llmRecBadge.style.borderColor = "var(--border-color)";
    llmScorePill.textContent = "SCORE: —";
    llmRoleFit.textContent = "—";
    llmExpFit.textContent = "—";
    llmTransFit.textContent = "—";
    llmSenFit.textContent = "—";
    llmProbObtain.textContent = "—";
    llmDiffUpside.textContent = "—";
    llmStrengthsList.innerHTML = `<li>Pending LLM evaluation</li>`;
    llmGapsList.innerHTML = `<li>Pending LLM evaluation</li>`;
    llmReasoning.textContent = "LLM evaluation for this opportunity has not been loaded.";
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

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


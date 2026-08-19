// Career OS — Human Review Workstation Frontend Logic with International Opportunity Eligibility Layer

let allJobs = [];
let humanDecisions = {}; // job_id -> { verdict, priority, notes, reviewed_at }
let currentQueueName = "Consider";
let currentEligFilter = "ALL_ELIGIBLE"; // Default view: India + International with explicit sponsorship
let currentFilteredJobs = [];
let currentJobIndex = 0;

// DOM Elements
const queueNav = document.getElementById("queueNav");
const eligNav = document.getElementById("eligNav");
const jobCard = document.getElementById("jobCard");
const jobQueueTag = document.getElementById("jobQueueTag");
const jobIdTag = document.getElementById("jobIdTag");
const jobGeoTag = document.getElementById("jobGeoTag");
const jobLocation = document.getElementById("jobLocation");
const jobSalary = document.getElementById("jobSalary");
const jobTitle = document.getElementById("jobTitle");
const jobCompany = document.getElementById("jobCompany");
const viewJobLink = document.getElementById("viewJobLink");

const eligibilityBanner = document.getElementById("eligibilityBanner");
const eligibilityBadge = document.getElementById("eligibilityBadge");
const eligibilityReason = document.getElementById("eligibilityReason");
const visaSignalTag = document.getElementById("visaSignalTag");
const relocSignalTag = document.getElementById("relocSignalTag");

const llmReasoning = document.getElementById("llmReasoning");
const candidateEvidence = document.getElementById("candidateEvidence");
const missingEvidence = document.getElementById("missingEvidence");

const strengthsList = document.getElementById("strengthsList");
const gapsList = document.getElementById("gapsList");

const overallScore = document.getElementById("overallScore");
const probObtaining = document.getElementById("probObtaining");
const roleFit = document.getElementById("roleFit");
const expFit = document.getElementById("expFit");
const transFit = document.getElementById("transFit");
const seniorityFit = document.getElementById("seniorityFit");
const oppAlign = document.getElementById("oppAlign");
const transDiff = document.getElementById("transDiff");
const careerUpside = document.getElementById("careerUpside");
const compUpside = document.getElementById("compUpside");

const decisionStatus = document.getElementById("decisionStatus");
const verdictButtons = document.querySelectorAll(".verdict-btn");
const priorityButtons = document.querySelectorAll(".priority-btn");
const humanNotes = document.getElementById("humanNotes");
const saveNextBtn = document.getElementById("saveNextBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

const queueListTitle = document.getElementById("queueListTitle");
const queueListScroll = document.getElementById("queueListScroll");

const globalProgress = document.getElementById("globalProgress");
const queueProgress = document.getElementById("queueProgress");

// Modals
const summaryBtn = document.getElementById("summaryBtn");
const summaryModal = document.getElementById("summaryModal");
const closeSummaryModal = document.getElementById("closeSummaryModal");
const shortcutsBtn = document.getElementById("shortcutsBtn");
const shortcutsModal = document.getElementById("shortcutsModal");
const closeShortcutsModal = document.getElementById("closeShortcutsModal");

let selectedVerdict = "";
let selectedPriority = "";

// Initialize App
async function initApp() {
  try {
    const res = await fetch("/api/data");
    const data = await res.json();
    allJobs = data.jobs || [];
    humanDecisions = data.decisions || {};
    
    updateFilterCounts();
    applyFilters();
  } catch (err) {
    console.error("Error loading review data:", err);
  }
}

// Set Queue Filter
function setQueue(queueName) {
  currentQueueName = queueName;
  document.querySelectorAll(".queue-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.queue === queueName);
  });
  applyFilters();
}

// Set Eligibility Filter
function setEligibilityFilter(eligName) {
  currentEligFilter = eligName;
  document.querySelectorAll(".elig-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.elig === eligName);
  });
  applyFilters();
}

// Apply Combined Filters (Queue + International Eligibility)
function applyFilters() {
  // Step 1: Filter by Queue Universe
  let queueUniverse = [];
  if (currentQueueName === "Consider") {
    queueUniverse = allJobs.filter(j => j.review_set === "Consider");
  } else if (currentQueueName === "Long Shot") {
    queueUniverse = allJobs.filter(j => j.review_set === "Long Shot");
  } else if (currentQueueName === "Skip Review") {
    queueUniverse = allJobs.filter(j => j.review_set && j.review_set.startsWith("Skip"));
  } else if (currentQueueName === "Reviewed") {
    queueUniverse = allJobs.filter(j => !!humanDecisions[j.job_id]?.verdict);
  } else if (currentQueueName === "Unreviewed") {
    queueUniverse = allJobs.filter(j => !humanDecisions[j.job_id]?.verdict);
  } else {
    // "All"
    queueUniverse = [...allJobs];
  }

  // Step 2: Filter by Eligibility Option
  if (currentEligFilter === "ALL_ELIGIBLE") {
    // Default view: India + International with explicit sponsorship/relocation
    currentFilteredJobs = queueUniverse.filter(j => j.international_eligibility === "ELIGIBLE");
  } else if (currentEligFilter === "INDIA") {
    currentFilteredJobs = queueUniverse.filter(j => j.geography === "INDIA");
  } else if (currentEligFilter === "INTL_SPONSORED") {
    currentFilteredJobs = queueUniverse.filter(j => j.international && j.international_eligibility === "ELIGIBLE");
  } else if (currentEligFilter === "INTL_UNKNOWN") {
    currentFilteredJobs = queueUniverse.filter(j => j.international && j.international_eligibility === "UNKNOWN");
  } else if (currentEligFilter === "INTL_EXCLUDED") {
    currentFilteredJobs = queueUniverse.filter(j => j.international && j.international_eligibility === "INELIGIBLE");
  } else {
    // "ALL_RAW"
    currentFilteredJobs = queueUniverse;
  }

  // Update dynamic count badges on buttons
  updateFilterCounts(queueUniverse);

  // Find first unreviewed job in this combined filter, or index 0
  const firstUnrevIdx = currentFilteredJobs.findIndex(j => !humanDecisions[j.job_id]?.verdict);
  currentJobIndex = firstUnrevIdx !== -1 ? firstUnrevIdx : 0;

  renderQueueList();
  renderCurrentJob();
  updateProgressUI();
}

// Update Filter Counts
function updateFilterCounts(currentQueueUniverse = null) {
  // Queue counts (reflecting overall dataset)
  const considerCount = allJobs.filter(j => j.review_set === "Consider").length;
  const longShotCount = allJobs.filter(j => j.review_set === "Long Shot").length;
  const skipCount = allJobs.filter(j => j.review_set && j.review_set.startsWith("Skip")).length;
  const totalCount = allJobs.length;
  const reviewedCount = Object.keys(humanDecisions).filter(id => !!humanDecisions[id]?.verdict).length;
  const unreviewedCount = totalCount - reviewedCount;

  document.getElementById("badgeConsider").textContent = considerCount;
  document.getElementById("badgeLongShot").textContent = longShotCount;
  document.getElementById("badgeSkip").textContent = skipCount;
  document.getElementById("badgeAll").textContent = totalCount;
  document.getElementById("badgeReviewed").textContent = reviewedCount;
  document.getElementById("badgeUnreviewed").textContent = unreviewedCount;

  // Eligibility counts (reflecting the currently active Queue Universe)
  const universeForElig = currentQueueUniverse || (
    currentQueueName === "Consider" ? allJobs.filter(j => j.review_set === "Consider") :
    currentQueueName === "Long Shot" ? allJobs.filter(j => j.review_set === "Long Shot") :
    currentQueueName === "Skip Review" ? allJobs.filter(j => j.review_set && j.review_set.startsWith("Skip")) :
    currentQueueName === "Reviewed" ? allJobs.filter(j => !!humanDecisions[j.job_id]?.verdict) :
    currentQueueName === "Unreviewed" ? allJobs.filter(j => !humanDecisions[j.job_id]?.verdict) :
    allJobs
  );

  const countAllEligible = universeForElig.filter(j => j.international_eligibility === "ELIGIBLE").length;
  const countIndia = universeForElig.filter(j => j.geography === "INDIA").length;
  const countIntlSponsored = universeForElig.filter(j => j.international && j.international_eligibility === "ELIGIBLE").length;
  const countIntlUnknown = universeForElig.filter(j => j.international && j.international_eligibility === "UNKNOWN").length;
  const countIntlExcluded = universeForElig.filter(j => j.international && j.international_eligibility === "INELIGIBLE").length;
  const countAllRaw = universeForElig.length;

  document.getElementById("eligBadgeAllEligible").textContent = countAllEligible;
  document.getElementById("eligBadgeIndia").textContent = countIndia;
  document.getElementById("eligBadgeIntlSponsored").textContent = countIntlSponsored;
  document.getElementById("eligBadgeIntlUnknown").textContent = countIntlUnknown;
  document.getElementById("eligBadgeIntlExcluded").textContent = countIntlExcluded;
  document.getElementById("eligBadgeAllRaw").textContent = countAllRaw;
}

// Render Job Card
function renderCurrentJob() {
  if (!currentFilteredJobs.length) {
    jobTitle.textContent = "No opportunities match the selected queue and eligibility filter.";
    jobCompany.textContent = "";
    jobQueueTag.textContent = `${currentQueueName} (0)`;
    jobIdTag.textContent = "--";
    jobGeoTag.textContent = currentEligFilter.replace("_", " ");
    jobLocation.textContent = "N/A";
    jobSalary.textContent = "N/A";
    
    eligibilityBanner.className = "eligibility-banner unknown";
    eligibilityBadge.textContent = "NO MATCH";
    eligibilityReason.textContent = "Try selecting 'All (Raw)' or 'International — Sponsorship Unknown' to view all discovered opportunities in this queue.";
    visaSignalTag.textContent = "Visa: N/A";
    relocSignalTag.textContent = "Relocation: N/A";

    llmReasoning.textContent = "No opportunities available for the selected filters.";
    candidateEvidence.textContent = "N/A";
    missingEvidence.textContent = "N/A";
    strengthsList.innerHTML = "";
    gapsList.innerHTML = "";
    overallScore.textContent = "--";
    probObtaining.textContent = "--";
    roleFit.textContent = "--";
    expFit.textContent = "--";
    transFit.textContent = "--";
    seniorityFit.textContent = "--";
    oppAlign.textContent = "--";
    setMetricBadge(transDiff, "unknown");
    setMetricBadge(careerUpside, "unknown");
    setMetricBadge(compUpside, "unknown");
    return;
  }

  const job = currentFilteredJobs[currentJobIndex];
  const ev = job.llm_evaluation || {};
  const currentDecision = humanDecisions[job.job_id] || {};

  // Meta Tags
  jobQueueTag.textContent = `${job.review_set || "Queue"} #${job.rank_in_set || (currentJobIndex + 1)}`;
  jobIdTag.textContent = job.job_id || "job_xxxx";
  jobGeoTag.textContent = (job.geography || "UNKNOWN").replace("_", " ");
  jobLocation.textContent = job.location || (job.is_remote ? "Remote" : "Location Not specified");
  
  const sMin = job.salary_min;
  const sMax = job.salary_max;
  if (sMin && sMax) {
    jobSalary.textContent = `$${sMin.toLocaleString()} - $${sMax.toLocaleString()}`;
    jobSalary.style.display = "inline-block";
  } else if (sMin) {
    jobSalary.textContent = `From $${sMin.toLocaleString()}`;
    jobSalary.style.display = "inline-block";
  } else if (sMax) {
    jobSalary.textContent = `Up to $${sMax.toLocaleString()}`;
    jobSalary.style.display = "inline-block";
  } else {
    jobSalary.style.display = "none";
  }

  jobTitle.textContent = job.title || "Untitled Opportunity";
  jobCompany.textContent = job.company || "Unknown Company";
  
  if (job.application_url) {
    viewJobLink.href = job.application_url;
    viewJobLink.style.display = "inline-flex";
  } else {
    viewJobLink.style.display = "none";
  }

  // Eligibility Banner Rendering
  const eligStatus = job.international_eligibility || "UNKNOWN";
  if (eligStatus === "ELIGIBLE") {
    eligibilityBanner.className = "eligibility-banner eligible";
    eligibilityBadge.textContent = job.is_home_country ? "HOME COUNTRY (ELIGIBLE)" : "INTERNATIONAL (ELIGIBLE)";
  } else if (eligStatus === "INELIGIBLE") {
    eligibilityBanner.className = "eligibility-banner ineligible";
    eligibilityBadge.textContent = "INTERNATIONAL (EXCLUDED)";
  } else {
    eligibilityBanner.className = "eligibility-banner unknown";
    eligibilityBadge.textContent = "SPONSORSHIP UNKNOWN";
  }

  eligibilityReason.textContent = job.eligibility_reason || "No explicit sponsorship or relocation data available.";
  visaSignalTag.textContent = `Visa: ${(job.visa_sponsorship_status || "UNKNOWN").replace("EXPLICITLY_", "")}`;
  relocSignalTag.textContent = `Reloc: ${(job.relocation_support_status || "UNKNOWN").replace("EXPLICITLY_", "")}`;

  // LLM Reasoning & Surfacing Bridge
  llmReasoning.textContent = ev.reasoning || "No evaluation reasoning available.";
  candidateEvidence.textContent = ev.evidence || "Not available";
  missingEvidence.textContent = ev.missing_evidence || "None flagged";

  // Key Strengths
  strengthsList.innerHTML = "";
  (ev.key_strengths || []).forEach(str => {
    const li = document.createElement("li");
    li.textContent = str;
    strengthsList.appendChild(li);
  });
  if (!(ev.key_strengths || []).length) {
    const li = document.createElement("li");
    li.textContent = "None specified";
    strengthsList.appendChild(li);
  }

  // Missing Critical Skills
  gapsList.innerHTML = "";
  (ev.missing_critical_skills || []).forEach(gap => {
    const li = document.createElement("li");
    li.textContent = gap;
    gapsList.appendChild(li);
  });
  if (!(ev.missing_critical_skills || []).length) {
    const li = document.createElement("li");
    li.textContent = "None flagged as critical blockers";
    gapsList.appendChild(li);
  }

  // Multi-dimensional Metrics
  overallScore.textContent = ev.overall_score !== undefined ? `${ev.overall_score}/100` : "--";
  probObtaining.textContent = ev.probability_of_obtaining !== undefined ? `${ev.probability_of_obtaining}%` : "--";
  roleFit.textContent = ev.role_fit !== undefined ? `${ev.role_fit}/100` : "--";
  expFit.textContent = ev.current_experience_fit !== undefined ? `${ev.current_experience_fit}/100` : "--";
  transFit.textContent = ev.transferable_capability_fit !== undefined ? `${ev.transferable_capability_fit}/100` : "--";
  seniorityFit.textContent = ev.seniority_fit !== undefined ? `${ev.seniority_fit}/100` : "--";
  oppAlign.textContent = ev.opportunity_alignment !== undefined ? `${ev.opportunity_alignment}/100` : "--";

  // Badges
  setMetricBadge(transDiff, ev.transition_difficulty || "unknown");
  setMetricBadge(careerUpside, ev.career_upside || "unknown");
  setMetricBadge(compUpside, ev.compensation_upside || "unknown");

  // Populate Decision Form
  selectedVerdict = currentDecision.verdict || "";
  selectedPriority = currentDecision.priority || "";
  humanNotes.value = currentDecision.notes || "";

  updateDecisionUIState();
  updateQueueListActiveItem();
}

function setMetricBadge(el, val) {
  el.textContent = val.replace("_", " ");
  el.className = "metric-badge";
  const lower = val.toLowerCase();
  if (lower === "high" || lower === "low") {
    el.classList.add(lower);
  } else if (lower === "medium") {
    el.classList.add("medium");
  } else if (lower === "very_high") {
    el.classList.add("very_high_diff");
  }
}

// Decision State UI
function updateDecisionUIState() {
  verdictButtons.forEach(btn => {
    btn.classList.toggle("selected", btn.dataset.verdict === selectedVerdict);
  });

  priorityButtons.forEach(btn => {
    btn.classList.toggle("selected", btn.dataset.priority === selectedPriority);
  });

  if (selectedVerdict) {
    decisionStatus.textContent = `Verdict: ${selectedVerdict}`;
    decisionStatus.className = "decision-status is-reviewed";
  } else {
    decisionStatus.textContent = "Unreviewed";
    decisionStatus.className = "decision-status";
  }
}

// Render Quick Jump Sidebar List
function renderQueueList() {
  const eligLabel = currentEligFilter === "ALL_ELIGIBLE" ? "Eligible" : currentEligFilter.replace("INTL_", "Intl ").replace("_", " ");
  queueListTitle.textContent = `${currentQueueName} • ${eligLabel} (${currentFilteredJobs.length})`;
  queueListScroll.innerHTML = "";

  currentFilteredJobs.forEach((job, idx) => {
    const item = document.createElement("div");
    item.className = "queue-item";
    if (idx === currentJobIndex) item.classList.add("active");

    const decision = humanDecisions[job.job_id];
    const verdict = decision?.verdict;
    const eligStatus = job.international_eligibility || "UNKNOWN";

    item.innerHTML = `
      <div class="queue-item-info">
        <span class="queue-item-title">${job.title || "Untitled"}</span>
        <span class="queue-item-sub">
          <span class="sub-elig-dot ${eligStatus}"></span>
          ${job.company || "Unknown"} • ${(job.geography || "UNKNOWN").replace("_", " ")} • Score: ${job.llm_evaluation?.overall_score || 0}
        </span>
      </div>
      <span class="queue-item-status ${verdict ? verdict : 'unreviewed'}">
        ${verdict ? verdict : '○'}
      </span>
    `;

    item.addEventListener("click", () => {
      currentJobIndex = idx;
      renderCurrentJob();
      updateProgressUI();
    });

    queueListScroll.appendChild(item);
  });
}

function updateQueueListActiveItem() {
  const items = queueListScroll.querySelectorAll(".queue-item");
  items.forEach((item, idx) => {
    item.classList.toggle("active", idx === currentJobIndex);
  });
  if (items[currentJobIndex]) {
    items[currentJobIndex].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

// Update Header Progress Pill
function updateProgressUI() {
  const total = allJobs.length;
  const reviewed = Object.keys(humanDecisions).filter(id => !!humanDecisions[id]?.verdict).length;
  globalProgress.textContent = `${reviewed} / ${total}`;

  const currentQueueTotal = currentFilteredJobs.length;
  const currentQueueReviewed = currentFilteredJobs.filter(j => !!humanDecisions[j.job_id]?.verdict).length;
  queueProgress.textContent = `(${currentQueueName}: ${currentQueueReviewed} / ${currentQueueTotal})`;
}

// Save Decision to Server
async function saveDecision(autoNext = true) {
  if (!currentFilteredJobs.length) return;
  const currentJob = currentFilteredJobs[currentJobIndex];
  if (!currentJob) return;

  const payload = {
    job_id: currentJob.job_id,
    verdict: selectedVerdict || "UNKNOWN",
    priority: selectedPriority || "MEDIUM",
    notes: humanNotes.value.trim()
  };

  try {
    const res = await fetch("/api/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (result.status === "success") {
      humanDecisions[currentJob.job_id] = result.decision;
      updateFilterCounts();
      updateProgressUI();
      renderQueueList();

      if (autoNext) {
        if (currentJobIndex < currentFilteredJobs.length - 1) {
          currentJobIndex++;
          renderCurrentJob();
        } else {
          const unrevIdx = currentFilteredJobs.findIndex(j => !humanDecisions[j.job_id]?.verdict);
          if (unrevIdx !== -1) {
            currentJobIndex = unrevIdx;
            renderCurrentJob();
          }
        }
      }
    }
  } catch (err) {
    console.error("Error saving decision:", err);
  }
}

// Event Listeners for Controls
verdictButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    selectedVerdict = btn.dataset.verdict;
    updateDecisionUIState();
  });
});

priorityButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    selectedPriority = selectedPriority === btn.dataset.priority ? "" : btn.dataset.priority;
    updateDecisionUIState();
  });
});

saveNextBtn.addEventListener("click", () => {
  saveDecision(true);
});

prevBtn.addEventListener("click", () => {
  if (currentJobIndex > 0) {
    currentJobIndex--;
    renderCurrentJob();
    updateProgressUI();
  }
});

nextBtn.addEventListener("click", () => {
  if (currentJobIndex < currentFilteredJobs.length - 1) {
    currentJobIndex++;
    renderCurrentJob();
    updateProgressUI();
  }
});

// Queue Nav
queueNav.addEventListener("click", (e) => {
  const btn = e.target.closest(".queue-btn");
  if (btn) {
    setQueue(btn.dataset.queue);
  }
});

// Elig Nav
eligNav.addEventListener("click", (e) => {
  const btn = e.target.closest(".elig-btn");
  if (btn) {
    setEligibilityFilter(btn.dataset.elig);
  }
});

// Summary Modal Logic
summaryBtn.addEventListener("click", () => {
  const total = allJobs.length;
  const reviewed = Object.keys(humanDecisions).filter(id => !!humanDecisions[id]?.verdict).length;
  document.getElementById("sumTotal").textContent = total;
  document.getElementById("sumReviewed").textContent = reviewed;
  document.getElementById("sumRemaining").textContent = total - reviewed;

  const verdicts = { APPLY: 0, MAYBE: 0, STRETCH: 0, SKIP: 0 };
  Object.values(humanDecisions).forEach(d => {
    if (verdicts[d.verdict] !== undefined) verdicts[d.verdict]++;
  });

  document.getElementById("countApply").textContent = verdicts.APPLY;
  document.getElementById("countMaybe").textContent = verdicts.MAYBE;
  document.getElementById("countStretch").textContent = verdicts.STRETCH;
  document.getElementById("countSkip").textContent = verdicts.SKIP;

  summaryModal.style.display = "flex";
});

closeSummaryModal.addEventListener("click", () => {
  summaryModal.style.display = "none";
});

shortcutsBtn.addEventListener("click", () => {
  shortcutsModal.style.display = "flex";
});

closeShortcutsModal.addEventListener("click", () => {
  shortcutsModal.style.display = "none";
});

[summaryModal, shortcutsModal].forEach(modal => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });
});

// Keyboard Shortcuts
window.addEventListener("keydown", (e) => {
  // Suppress shortcuts when typing in inputs/textareas
  const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
  if (activeTag === "textarea" || activeTag === "input") {
    if (e.key === "Escape") {
      document.activeElement.blur();
    }
    return;
  }

  const key = e.key.toUpperCase();

  if (key === "A") {
    e.preventDefault();
    selectedVerdict = "APPLY";
    updateDecisionUIState();
  } else if (key === "M") {
    e.preventDefault();
    selectedVerdict = "MAYBE";
    updateDecisionUIState();
  } else if (key === "T") {
    e.preventDefault();
    selectedVerdict = "STRETCH";
    updateDecisionUIState();
  } else if (key === "X") {
    e.preventDefault();
    selectedVerdict = "SKIP";
    updateDecisionUIState();
  } else if (key === "H") {
    e.preventDefault();
    selectedPriority = selectedPriority === "HIGH" ? "MEDIUM" : "HIGH";
    updateDecisionUIState();
  } else if (key === "ENTER") {
    e.preventDefault();
    saveDecision(true);
  } else if (key === "N") {
    e.preventDefault();
    if (currentJobIndex < currentFilteredJobs.length - 1) {
      currentJobIndex++;
      renderCurrentJob();
      updateProgressUI();
    }
  } else if (key === "P") {
    e.preventDefault();
    if (currentJobIndex > 0) {
      currentJobIndex--;
      renderCurrentJob();
      updateProgressUI();
    }
  } else if (key === "?" || e.key === "?") {
    shortcutsModal.style.display = shortcutsModal.style.display === "flex" ? "none" : "flex";
  } else if (e.key === "Escape") {
    summaryModal.style.display = "none";
    shortcutsModal.style.display = "none";
  }
});

// Boot
document.addEventListener("DOMContentLoaded", initApp);

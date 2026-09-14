'use strict';
const toggle = document.querySelector('.menu-toggle');
const mobileNav = document.getElementById('mobile-nav');
function closeMenu(focus) {
  if (!toggle || !mobileNav) return;
  mobileNav.hidden = true;
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', 'Open navigation');
  if (focus) toggle.focus();
}
if (toggle && mobileNav) {
  toggle.addEventListener('click', function () {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    mobileNav.hidden = !open;
  });
  mobileNav.addEventListener('click', function (event) {
    if (event.target.closest('a')) closeMenu(false);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !mobileNav.hidden) closeMenu(true);
  });
}
const search = document.getElementById('case-search');
const cards = Array.from(document.querySelectorAll('.case-card[data-search]'));
const filters = Array.from(document.querySelectorAll('[data-filter]'));
let category = 'All';
function applyFilters() {
  const words = (search ? search.value : '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  let count = 0;
  cards.forEach(function (card) {
    const shown = (category === 'All' || card.dataset.category === category) && words.every(function (word) { return card.dataset.search.includes(word); });
    card.hidden = !shown;
    if (shown) count++;
  });
  const status = document.getElementById('result-count');
  if (status) status.textContent = count + (count === 1 ? ' case ' : ' cases ') + (words.length || category !== 'All' ? 'matching your filters' : 'in the collection');
  const empty = document.getElementById('no-results');
  if (empty) empty.hidden = count !== 0;
}
filters.forEach(function (button) {
  button.addEventListener('click', function () {
    category = button.dataset.filter;
    filters.forEach(function (other) { other.setAttribute('aria-pressed', String(other === button)); });
    applyFilters();
  });
});
if (search) search.addEventListener('input', applyFilters);
const reset = document.getElementById('reset-search');
if (reset) reset.addEventListener('click', function () {
  category = 'All'; search.value = '';
  filters.forEach(function (button) { button.setAttribute('aria-pressed', String(button.dataset.filter === 'All')); });
  applyFilters(); search.focus();
});
const dialog = document.getElementById('capture-dialog');
const zoom = document.querySelector('[data-zoom]');
const closeDialog = document.querySelector('[data-close-dialog]');
if (zoom && dialog) zoom.addEventListener('click', function () { dialog.showModal(); });
if (closeDialog && dialog) closeDialog.addEventListener('click', function () { dialog.close(); });
if (dialog) dialog.addEventListener('click', function (event) { if (event.target === dialog) dialog.close(); });
const share = document.querySelector('[data-share]');
if (share) share.addEventListener('click', async function () {
  const status = document.getElementById('share-status');
  const url = document.querySelector('link[rel=canonical]').href;
  try { await navigator.clipboard.writeText(url); status.textContent = 'Case link copied.'; }
  catch (error) { status.textContent = 'Copy this link: ' + url; status.style.overflowWrap = 'anywhere'; }
});
const form = document.getElementById('contribution-form');
if (form) {
  const urlField = document.getElementById('report-url');
  const lessonField = document.getElementById('lesson');
  const sourceNameField = document.getElementById('source-name');
  const creditField = document.getElementById('credit');
  const review = document.getElementById('contribution-review');
  const status = document.getElementById('form-status');
  const caseParam = new URLSearchParams(location.search).get('case');
  const caseId = /^SA-\d{3}$/.test(caseParam || '') ? caseParam : null;
  let draft = '';
  if (caseId) {
    const note = document.getElementById('correction-notice');
    note.textContent = 'Improving case ' + caseId + '. Include a public source that supports your correction.';
    note.hidden = false;
  }
  form.addEventListener('input', function () {
    urlField.setCustomValidity(''); lessonField.setCustomValidity('');
    draft = ''; review.hidden = true; status.textContent = '';
  });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    let url;
    try {
      url = new URL(urlField.value.trim());
      if (!['https:', 'http:'].includes(url.protocol) || !url.hostname || url.username || url.password) throw new Error('Invalid report URL');
    } catch (error) {
      urlField.setCustomValidity('Enter a public http or https report link, without login details.');
      urlField.reportValidity(); return;
    }
    const lesson = lessonField.value.trim();
    if (!lesson) { lessonField.setCustomValidity('Add a short lesson or correction.'); lessonField.reportValidity(); return; }
    const sourceName = sourceNameField.value.trim() || url.hostname;
    const credit = creditField.value.trim() || 'Anonymous';
    const title = caseId ? 'Correction to ' + caseId : 'New case contribution';
    document.getElementById('review-title').textContent = title;
    document.getElementById('review-lesson').textContent = lesson;
    const source = document.getElementById('review-source');
    source.href = url.href; source.textContent = sourceName + ' · ' + url.hostname;
    document.getElementById('review-credit').textContent = 'Contributor credit: ' + credit;
    draft = ['# ' + title, '', 'Public report: ' + url.href, 'Source name (to verify): ' + sourceName, '', '## Lesson or correction', lesson, '', 'Contributor credit: ' + credit, '', 'For editorial review; not a verified finding.'].join('\n');
    const subject = '[' + form.dataset.project + '] ' + title;
    document.getElementById('email-submit').href = 'mailto:' + form.dataset.email + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(draft);
    const github = document.getElementById('github-submit');
    if (github && /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+$/.test(form.dataset.repository)) {
      const fields = caseId
        ? {template: 'correction.yml', title: subject, case: caseId, source: url.href, correction: lesson}
        : {template: 'new-example.yml', title: subject, report: url.href, lesson: lesson, source: sourceName, credit: credit};
      github.href = form.dataset.repository + '/issues/new?' + new URLSearchParams(fields).toString();
      github.hidden = false;
    }
    review.hidden = false;
    status.textContent = 'Draft ready below. Review it, then choose how to send it.';
    review.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest'});
  });
  document.getElementById('download-contribution').addEventListener('click', function () {
    if (!draft) return;
    const url = URL.createObjectURL(new Blob([draft + '\nStatus: local draft, not submitted or reviewed.\n'], {type: 'text/markdown;charset=utf-8'}));
    const a = document.createElement('a');
    a.href = url; a.download = caseId ? caseId + '-correction.md' : 'case-contribution.md';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });
}


// Visitors choose the evidence they want to examine; nothing rotates automatically.
const showcaseChoices = Array.from(document.querySelectorAll('[data-showcase]'));
const showcaseGroup = document.querySelector('.showcase-choices');
if (showcaseGroup && showcaseChoices.length) {
  showcaseGroup.hidden = false;
  showcaseChoices.forEach(function (button) {
    button.addEventListener('click', function () {
      showcaseChoices.forEach(function (other) { other.setAttribute('aria-pressed', String(other === button)); });
      const capture = document.getElementById('showcase-image');
      capture.src = button.dataset.image;
      capture.alt = button.dataset.alt;
      document.getElementById('showcase-image-link').href = button.dataset.link;
      document.getElementById('showcase-case-link').href = button.dataset.link;
      document.getElementById('showcase-image-link').setAttribute('aria-label', 'Read case: ' + button.dataset.headline);
      document.getElementById('showcase-headline').textContent = button.dataset.headline;
      document.getElementById('showcase-summary').textContent = button.dataset.summary;
      document.getElementById('showcase-assessment').textContent = button.dataset.assessment;
    });
  });
}

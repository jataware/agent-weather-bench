(() => {
  'use strict';
  const task = JSON.parse(document.getElementById('task-data').textContent);
  const key = `agent-weather-bench:review:${task.task}:${task.version}`;
  const controls = [...document.querySelectorAll('[data-field]')];
  const status = document.getElementById('save-status');
  const warning = document.getElementById('source-warning');
  let fields = {}, updatedAt = null, reviewFingerprint = task.fingerprint, storageAvailable = true;

  function warn(message) { warning.textContent = message; warning.hidden = !message; }
  function refresh() {
    const count = task.leaves.filter(leaf => Object.entries(fields).some(([name, value]) => name.startsWith(`rubric.${leaf.id}.`) && value.trim())).length;
    document.getElementById('review-progress').textContent = `${count} of ${task.leaves.length} rubric checks have feedback`;
    for (const leaf of task.leaves) {
      const hasNote = Object.entries(fields).some(([name, value]) => name.startsWith(`rubric.${leaf.id}.`) && value.trim());
      document.querySelector(`#leaf-${leaf.id} .note-dot`).hidden = !hasNote;
    }
  }
  function fill() {
    controls.forEach(control => { control.value = fields[control.dataset.field] || ''; });
    refresh();
  }
  function record() {
    return {review_schema_version: 1, task: task.task, task_version: task.version, source_fingerprint: reviewFingerprint,
      source_hashes: reviewFingerprint === task.fingerprint ? task.source_hashes : originalHashes,
      updated_at: updatedAt, fields: {...fields}};
  }
  let originalHashes = task.source_hashes;
  function save() {
    updatedAt = new Date().toISOString();
    try { localStorage.setItem(key, JSON.stringify(record())); storageAvailable = true; }
    catch { storageAvailable = false; }
    status.textContent = storageAvailable ? 'Saved in this browser' : 'Browser storage unavailable — export to save';
    refresh();
  }
  function validateRecord(value) {
    if (!value || value.review_schema_version !== 1 || value.task !== task.task || value.task_version !== task.version ||
        !value.fields || typeof value.fields !== 'object' || Array.isArray(value.fields) ||
        typeof value.source_fingerprint !== 'string' || !value.source_hashes || typeof value.source_hashes !== 'object' ||
        !Object.values(value.fields).every(item => typeof item === 'string')) {
      throw new Error('Choose a review JSON exported from this task and version.');
    }
    return value;
  }
  function load(value) {
    validateRecord(value);
    fields = Object.fromEntries(Object.entries(value.fields).filter(([name]) => controls.some(control => control.dataset.field === name)));
    updatedAt = value.updated_at;
    reviewFingerprint = value.source_fingerprint;
    originalHashes = value.source_hashes;
    fill();
    warn(reviewFingerprint !== task.fingerprint ? 'These notes refer to an earlier source snapshot. Compare the exported hashes before applying them to this draft.' : '');
  }
  try {
    const previous = localStorage.getItem(key);
    if (previous) load(JSON.parse(previous));
    status.textContent = previous ? 'Restored from this browser' : 'Notes will save in this browser';
  } catch { storageAvailable = false; status.textContent = 'Could not restore browser notes — export to save'; }
  refresh();
  controls.forEach(control => control.addEventListener('input', () => {
    fields[control.dataset.field] = control.value;
    save();
  }));

  function download(content, extension, type) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${task.task}-critique.${extension}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function markdown() {
    const lines = [`# Critique: ${task.title}`, '', `Task: ${task.task} (${task.version})`, `Reviewer: ${fields.reviewer || 'Not specified'}`,
      `Recommendation: ${fields.recommendation || 'Not specified'}`, `Updated: ${updatedAt || 'No edits yet'}`, `Source fingerprint: ${reviewFingerprint}`, '',
      'These are review notes, not approval or benchmark results.', ''];
    for (const [name, label] of Object.entries({summary:'Main changes', questions:'Questions for discussion', design:'Task design', prompt:'Agent prompt', scoring:'Scoring', sources:'Sources and inputs'})) {
      if (fields[name]?.trim()) lines.push(`## ${label}`, '', fields[name], '');
    }
    const reviewed = task.leaves.filter(leaf => ['decision','weight','required','comment'].some(name => fields[`rubric.${leaf.id}.${name}`]?.trim()));
    if (reviewed.length) lines.push('## Rubric feedback', '');
    for (const leaf of reviewed) {
      const base = `rubric.${leaf.id}`;
      lines.push(`### ${leaf.id}`, '', `Current criterion: ${leaf.criterion}`, '');
      for (const [name, label] of Object.entries({decision:'Criterion',weight:'Suggested sibling weight',required:'Suggested required status',comment:'Reason / proposed wording'})) {
        if (fields[`${base}.${name}`]?.trim()) lines.push(`${label}: ${fields[`${base}.${name}`]}`, '');
      }
    }
    lines.push('## Source hashes', '', '```json', JSON.stringify(record().source_hashes, null, 2), '```', '');
    return lines.join('\n');
  }
  document.getElementById('export-md').addEventListener('click', () => download(markdown(), 'md', 'text/markdown;charset=utf-8'));
  document.getElementById('export-json').addEventListener('click', () => download(JSON.stringify(record(), null, 2) + '\n', 'json', 'application/json'));
  const fileInput = document.getElementById('import-file');
  document.getElementById('import-notes').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const value = validateRecord(JSON.parse(await file.text()));
      if (Object.values(fields).some(v => v.trim()) && !confirm('Replace the notes currently on this page with the imported review? Export first if you want to keep them.')) return;
      load(value); save();
    } catch (error) { warn(`Import failed: ${error.message}`); }
    finally { fileInput.value = ''; }
  });
  document.getElementById('clear-notes').addEventListener('click', () => {
    if (!confirm('Clear this task’s local review notes? Export first if you want to keep them.')) return;
    fields = {}; updatedAt = null; reviewFingerprint = task.fingerprint; originalHashes = task.source_hashes;
    try { localStorage.removeItem(key); } catch {}
    warn(''); fill(); status.textContent = 'Local review cleared';
  });
})();

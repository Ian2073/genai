(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  async function apiGet(url) {
    const res = await fetch(url, {cache: 'no-store'});
    const data = await res.json();
    if (!res.ok || (data && data.ok === false && data.error)) {
      throw new Error((data && data.error) || ('GET failed: ' + url));
    }
    return data;
  }

  async function apiPost(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      cache: 'no-store',
      body: JSON.stringify(payload || {}),
    });
    const data = await res.json();
    if (!res.ok || (data && data.ok === false && data.error)) {
      throw new Error((data && data.error) || ('POST failed: ' + url));
    }
    return data;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeDomId(value) {
    return String(value == null ? '' : value).replace(/[^a-zA-Z0-9_-]+/g, '_');
  }

  const state = {
    templates: [],
    focusedGraph: null,
    previewData: null,
    evidenceData: null,
    activeView: 'overview',
    activePromptMode: 'g0',
    presentationMode: false,
  };

  function collectFormData() {
    return {
      age: byId('age').value || '4-5',
      category: byId('category').value || 'educational',
      subcategory: byId('subcategory').value || 'science',
      theme: byId('theme').value || 'mystery',
      story_input_mode: byId('story_input_mode').value || 'custom',
      story_prompt: (byId('story_prompt').value || '').trim(),
      story_materials: (byId('story_materials').value || '').trim(),
      preview_step: byId('preview_step').value || 'story_plan',
      preview_page: parseInt(byId('preview_page').value || '4', 10) || 4,
    };
  }

  function switchView(viewId) {
    state.activeView = viewId;
    document.querySelectorAll('[data-demo-view]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-demo-view') === viewId);
    });
    document.querySelectorAll('[data-panel]').forEach(function (panel) {
      const isActive = panel.getAttribute('data-panel') === viewId;
      panel.classList.toggle('active', isActive);
      panel.hidden = !isActive;
    });
  }

  function setPresentationMode(enabled) {
    state.presentationMode = Boolean(enabled);
    document.body.classList.toggle('presentation-mode', state.presentationMode);
    const button = byId('btn_presentation_mode');
    if (button) {
      button.textContent = state.presentationMode ? 'Exit Presentation Mode' : 'Presentation Mode';
    }
  }

  function renderTemplates(templates) {
    const select = byId('saved_template_select');
    state.templates = Array.isArray(templates) ? templates : [];
    select.innerHTML = '<option value="">不套用</option>';
    state.templates.forEach(function (item, index) {
      const opt = document.createElement('option');
      opt.value = String(index);
      opt.textContent = String(item.name || ('Template ' + String(index + 1)));
      select.appendChild(opt);
    });
  }

  function applySelectedTemplate() {
    const idx = parseInt(byId('saved_template_select').value || '', 10);
    if (!Number.isFinite(idx) || !state.templates[idx]) return;
    const item = state.templates[idx];
    byId('story_prompt').value = String(item.prompt || '');
    byId('story_materials').value = String(item.story_materials || '');
    byId('story_input_mode').value = String(item.story_input_mode || 'custom');
    byId('preview_status').textContent = '已套用使用者模板，可直接更新 preview。';
  }

  const CONTROL_MATRIX_MODES = [
    {id: 'g0', label: 'G0', title: 'Baseline', subtitle: '無結構化控制'},
    {id: 'g1', label: 'G1', title: 'KG Only', subtitle: '加入知識先驗'},
    {id: 'g2', label: 'G2', title: 'Structured Control', subtitle: '完整結構化控制'},
  ];

  const CONTROL_MATRIX_DIMENSIONS = [
    {key: 'basics', label: '基礎故事條件', detail: '主題 / 類別 / 年齡 / 頁數', g0: true, g1: true, g2: true},
    {key: 'kg_prior', label: '知識先驗 (KG)', detail: '角色 / 場景 / Moral / Guidelines', g0: false, g1: true, g2: true},
    {key: 'format', label: '輸出格式約束', detail: '標籤 / 章節數 / 規範段落', g0: false, g1: false, g2: true},
    {key: 'structure', label: '章節結構規則', detail: 'Arc / Turning Point / 分幕', g0: false, g1: false, g2: true},
    {key: 'consistency', label: '場景與狀態一致性', detail: 'Page Structure / Visual / State', g0: false, g1: false, g2: true},
  ];

  const DEFENSE_SCRIPT_STEPS = [
    {
      title: '1. 先界定問題',
      body: '一般生成只給主題，控制力弱；我的 demo 先用 G0 顯示 baseline 的限制。',
      tab: 'prompt',
    },
    {
      title: '2. 再展示知識先驗',
      body: 'G1 加入 KG，角色、場景、moral 與教學目標不再是模型隨機想像。',
      tab: 'kg',
    },
    {
      title: '3. 最後展示結構化控制',
      body: 'G2 把 page structure、branch context、scene state 放進 prompt，控制每頁該做什麼。',
      tab: 'control',
    },
    {
      title: '4. 用證據回答一致性',
      body: '如果輸出不符合格式或狀態，validation 會產生 retry guidance，並留下 log 和 prompt files。',
      tab: 'evidence',
    },
  ];

  const CONTROL_PROOF_ITEMS = [
    {
      id: 'user',
      title: '使用者控制',
      question: '使用者到底控制什麼？',
      answer: '年齡、類別、子類別、主題、custom prompt、materials 會先被正規化，再併入 effective guidelines。',
      evidence: 'User Intent / Effective Guidelines',
    },
    {
      id: 'kg',
      title: 'KG 約束',
      question: 'KG 怎麼參與？',
      answer: 'KG 不只顯示節點，而是提供角色、場景、moral、variation 與 branch candidates 作為生成先驗。',
      evidence: 'KG Selection / KG Prompt Guidelines',
    },
    {
      id: 'structure',
      title: '頁面結構控制',
      question: '怎麼控制故事流程？',
      answer: '每頁有 page structure 與 page function，讓模型知道這頁是 setup、action、turning point 或 resolution。',
      evidence: 'Page Structure Sample',
    },
    {
      id: 'state',
      title: '一致性控制',
      question: '怎麼避免前後矛盾？',
      answer: 'visual / state context 會把角色狀態、場景狀態與頁面連續性帶入下一步生成。',
      evidence: 'Visual / State Context',
    },
    {
      id: 'multimodal',
      title: '多模態銜接',
      question: '文字、圖像、聲音怎麼連起來？',
      answer: '文字階段先產生可追蹤的 page plan / prompt，後續 image、translation、voice 模組可用同一批 story resources。',
      evidence: 'Page Prompt Files / Character Prompt Files',
    },
    {
      id: 'retry',
      title: '驗證與重試',
      question: '失敗時怎麼修正？',
      answer: 'validation failure 會產生 retry guidance，下一次 prompt 會帶入具體 feedback，而不是盲目重跑。',
      evidence: 'Retry Guidance / Log Events',
    },
  ];

  function renderControlMatrix() {
    const target = byId('control_matrix');
    if (!target) return;
    const header = (
      '<div class="matrix-row header">' +
        '<div class="matrix-cell label">控制維度</div>' +
        CONTROL_MATRIX_MODES.map(function (mode) {
          return (
            '<div class="matrix-cell mode ' + escapeHtml(mode.id) + '">' +
              '<span class="matrix-mode-id">' + escapeHtml(mode.label) + '</span>' +
              '<span class="matrix-mode-title">' + escapeHtml(mode.title) + '</span>' +
              '<span class="matrix-mode-subtitle">' + escapeHtml(mode.subtitle) + '</span>' +
            '</div>'
          );
        }).join('') +
      '</div>'
    );
    const rows = CONTROL_MATRIX_DIMENSIONS.map(function (dim) {
      const labelCell = (
        '<div class="matrix-cell label">' +
          '<strong>' + escapeHtml(dim.label) + '</strong>' +
          '<small>' + escapeHtml(dim.detail) + '</small>' +
        '</div>'
      );
      const cells = CONTROL_MATRIX_MODES.map(function (mode) {
        const on = Boolean(dim[mode.id]);
        return (
          '<div class="matrix-cell value ' + (on ? 'on' : 'off') + '">' +
            '<span class="matrix-check">' + (on ? '✓' : '–') + '</span>' +
          '</div>'
        );
      }).join('');
      return '<div class="matrix-row">' + labelCell + cells + '</div>';
    }).join('');
    target.innerHTML = header + rows;
  }

  function renderDefenseScript() {
    const node = byId('defense_script');
    if (!node) return;
    node.innerHTML = DEFENSE_SCRIPT_STEPS.map(function (step, index) {
      return (
        '<button class="defense-step" data-demo-jump="' + escapeHtml(step.tab) + '" type="button">' +
          '<span class="defense-step-index">' + String(index + 1) + '</span>' +
          '<span class="defense-step-body">' +
            '<strong>' + escapeHtml(step.title) + '</strong>' +
            '<small>' + escapeHtml(step.body) + '</small>' +
          '</span>' +
        '</button>'
      );
    }).join('');
    node.querySelectorAll('[data-demo-jump]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchView(btn.getAttribute('data-demo-jump') || 'overview');
      });
    });
  }

  function renderControlProof(data, evidenceData) {
    const node = byId('control_proof_grid');
    if (!node) return;
    const preview = (data || {}).preview || {};
    const retry = preview.retry_summary || {};
    const evidenceRetry = (evidenceData || {}).retry || {};
    const dynamicValues = {
      user: collectFormData().story_input_mode || '-',
      kg: (((data || {}).profile || {}).focused_graph || {}).nodes ? String((((data || {}).profile || {}).focused_graph || {}).nodes.length) + ' nodes' : '-',
      structure: preview.preview_step ? String(preview.preview_step) + ' / page ' + String(preview.preview_page || '-') : '-',
      state: preview.visual_context ? 'context ready' : '-',
      multimodal: state.evidenceData ? 'resources loaded' : 'pending evidence',
      retry: 'max ' + String(retry.configured_max_retries || 0) + ' / observed ' + String(evidenceRetry.retry_attempts || 0),
    };
    node.innerHTML = CONTROL_PROOF_ITEMS.map(function (item) {
      return (
        '<article class="control-proof-item proof-' + escapeHtml(item.id) + '">' +
          '<div class="control-proof-head">' +
            '<span class="control-proof-title">' + escapeHtml(item.title) + '</span>' +
            '<span class="control-proof-metric">' + escapeHtml(dynamicValues[item.id] || '-') + '</span>' +
          '</div>' +
          '<div class="control-proof-question">' + escapeHtml(item.question) + '</div>' +
          '<div class="control-proof-answer">' + escapeHtml(item.answer) + '</div>' +
          '<div class="control-proof-evidence">證據: ' + escapeHtml(item.evidence) + '</div>' +
        '</article>'
      );
    }).join('');
  }

  function renderOverview() {
    const previewData = state.previewData || {};
    const evidenceData = state.evidenceData || {};
    const profile = previewData.profile || {};
    const preview = previewData.preview || {};
    const retry = preview.retry_summary || {};
    const modes = preview.modes || [];

    renderControlMatrix();
    renderResearchClaims();
    renderPipelineFlow();
    renderDefenseScript();

    const retryAttempts = ((evidenceData || {}).retry || {}).retry_attempts || 0;
    const validationFailures = ((evidenceData || {}).retry || {}).validation_failures || 0;

    byId('overview_story_snapshot').innerHTML = [
      ['主題', profile.theme_label || '-'],
      ['展示模式', String(modes.length || 0) + ' 種'],
      ['預期頁數', String(profile.pages_expected || '-')],
      ['Input Mode', collectFormData().story_input_mode || '-'],
      ['Preview Step', preview.preview_step || '-'],
      ['Preview Page', preview.preview_page || '-'],
      ['Story Root', evidenceData.story_root || '-'],
      ['Retry Count', (evidenceData.retry || {}).retry_attempts || 0],
      ['Validation Failures', (evidenceData.retry || {}).validation_failures || 0],
    ].map(function (pair) {
      var w = (pair[0] === 'Story Root') ? ' wide' : '';
      return '<div class="mini' + w + '"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
    }).join('');

    const chips = [];
    if (profile.category_label) chips.push('<span class="chip">類別: ' + escapeHtml(profile.category_label) + '</span>');
    if (profile.subcategory_label) chips.push('<span class="chip">子類別: ' + escapeHtml(profile.subcategory_label) + '</span>');
    if (profile.theme_label) chips.push('<span class="chip">主題: ' + escapeHtml(profile.theme_label) + '</span>');
    if (profile.visual_style) chips.push('<span class="chip">Visual Style: ' + escapeHtml(profile.visual_style) + '</span>');
    (profile.characters || []).slice(0, 3).forEach(function (item) {
      chips.push('<span class="chip">角色: ' + escapeHtml(item) + '</span>');
    });
    byId('overview_control_chips').innerHTML = chips.join('') || '<span class="chip">目前沒有摘要資料</span>';
  }

  function uniqueStrings(values) {
    const seen = new Set();
    return (values || []).filter(function (value) {
      const key = String(value || '');
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function extractPlaceholders(text) {
    return uniqueStrings(String(text || '').match(/\{[^{}\n]+\}/g) || []);
  }

  function highlightPlaceholders(text) {
    return escapeHtml(text || '').replace(/\{[^{}\n]+\}/g, function (match) {
      return '<span class="ph-mark">' + match + '</span>';
    });
  }

  const RESEARCH_CLAIMS = [
    {id: 'kg', label: 'Knowledge Prior', title: '知識先驗注入 (KG)', detail: '以知識圖譜收斂故事素材與角色關係，降低生成時的知識漂移。', mapTo: 'G1'},
    {id: 'structured', label: 'Structured Control', title: '結構化 Prompt 控制', detail: '在模板層強制章節、轉折與輸出格式，讓產出可以被解析與驗證。', mapTo: 'G2'},
    {id: 'retry', label: 'Validate & Repair', title: '驗證式 Retry 與修復', detail: '失敗時帶入 feedback 重試並可針對性修復，降低落盤失敗率。', mapTo: 'Retry Loop'},
  ];

  const PIPELINE_FLOW = [
    {id: 'input', label: 'Input', sub: '年齡 / 類別 / 主題', tab: 'overview'},
    {id: 'kg', label: 'KG Selection', sub: '角色 / 場景 / 變體', tab: 'kg'},
    {id: 'prompt', label: 'Prompt Assembly', sub: 'G0 / G1 / G2 模板', tab: 'prompt'},
    {id: 'control', label: 'Generate + Validate', sub: '結構化驗證 / Retry', tab: 'control'},
    {id: 'evidence', label: 'Evidence', sub: '落盤檔案 / 事件', tab: 'evidence'},
  ];

  function renderResearchClaims() {
    const node = byId('research_claims');
    if (!node) return;
    node.innerHTML = RESEARCH_CLAIMS.map(function (claim, index) {
      return (
        '<div class="claim-card claim-' + escapeHtml(claim.id) + '">' +
          '<div class="claim-index">' + String(index + 1) + '</div>' +
          '<div class="claim-body">' +
            '<div class="claim-head">' +
              '<span class="claim-label">' + escapeHtml(claim.label) + '</span>' +
              '<span class="claim-pill">' + escapeHtml(claim.mapTo) + '</span>' +
            '</div>' +
            '<div class="claim-title">' + escapeHtml(claim.title) + '</div>' +
            '<div class="claim-detail">' + escapeHtml(claim.detail) + '</div>' +
          '</div>' +
        '</div>'
      );
    }).join('');
  }

  function renderPipelineFlow() {
    const node = byId('pipeline_flow');
    if (!node) return;
    node.innerHTML = PIPELINE_FLOW.map(function (step, index) {
      const arrow = index < PIPELINE_FLOW.length - 1 ? '<div class="pipeline-arrow">→</div>' : '';
      return (
        '<button class="pipeline-step" data-demo-jump="' + escapeHtml(step.tab) + '" type="button">' +
          '<div class="pipeline-step-index">' + String(index + 1) + '</div>' +
          '<div class="pipeline-step-body">' +
            '<div class="pipeline-step-label">' + escapeHtml(step.label) + '</div>' +
            '<div class="pipeline-step-sub">' + escapeHtml(step.sub) + '</div>' +
          '</div>' +
        '</button>' + arrow
      );
    }).join('');
    node.querySelectorAll('[data-demo-jump]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchView(btn.getAttribute('data-demo-jump') || 'overview');
      });
    });
  }

  function promptSignalsForMode(mode) {
    const text = [
      mode.raw_system || '',
      mode.raw_user || '',
      mode.filled_system || '',
      mode.filled_user || '',
    ].join('\n');
    const checks = [
      {id: 'kg', label: 'KG', pattern: /\bkg_|characters_csv|kg_scenes|kg_guidelines|kg_moral/i},
      {id: 'scene', label: 'Scene Context', pattern: /scene_|page_structure|visual_context|smart_context/i},
      {id: 'branch', label: 'Branch Control', pattern: /branch_|interaction_plan/i},
      {id: 'system', label: 'System Assumptions', pattern: /system_core_assumptions|system_assumptions/i},
      {id: 'state', label: 'State Control', pattern: /state_card|state context|consisten/i},
      {id: 'user', label: 'User Input', pattern: /theme|category|subcategory|age_group|story_prompt|materials/i},
    ];
    return checks.filter(function (item) {
      return item.pattern.test(text);
    }).map(function (item) {
      return item.label;
    });
  }

  function promptNotesForMode(mode) {
    const byMode = {
      g0: ['Baseline 無結構化控制', '主要提供最基本的故事主題與年齡條件。'],
      g1: ['加入 KG 知識先驗（角色、場景）', '提供較完整的故事背景與語意素材。'],
      g2: ['結合 KG 與結構化控制（頁面結構、場景狀態）', '進一步約束輸出格式、章節轉折與場景一致性。'],
    };
    return byMode[String(mode.id || '').toLowerCase()] || [String(mode.description || '此模式提供不同層級的 prompt 控制。')];
  }

  function controlLevelForMode(mode) {
    const modeId = String(mode.id || '').toLowerCase();
    if (modeId === 'g0') return 'Baseline';
    if (modeId === 'g1') return 'KG Only';
    if (modeId === 'g2') return 'Structured Control';
    return 'Custom';
  }

  const MODE_CAPABILITIES = {
    g0: {basics: true, kg: false, format: false, structure: false, consistency: false},
    g1: {basics: true, kg: true, format: false, structure: false, consistency: false},
    g2: {basics: true, kg: true, format: true, structure: true, consistency: true},
  };

  const CAPABILITY_LABELS = [
    {key: 'basics', short: '基礎', full: '基礎故事條件'},
    {key: 'kg', short: 'KG', full: '知識先驗'},
    {key: 'format', short: '格式', full: '格式約束'},
    {key: 'structure', short: '結構', full: '章節結構'},
    {key: 'consistency', short: '一致', full: '場景一致性'},
  ];

  function capabilityDotsHtml(modeId) {
    const modeKey = String(modeId || '').toLowerCase();
    const cap = MODE_CAPABILITIES[modeKey] || {};
    return (
      '<div class="capability-dots">' +
        CAPABILITY_LABELS.map(function (item) {
          const on = Boolean(cap[item.key]);
          return (
            '<span class="capability-dot ' + (on ? 'on' : 'off') + '" title="' + escapeHtml(item.full) + '">' +
              '<i class="dot"></i>' +
              '<span class="dot-label">' + escapeHtml(item.short) + '</span>' +
            '</span>'
          );
        }).join('') +
      '</div>'
    );
  }

  function structuralConstraintLevel(mode) {
    const text = [mode.raw_system || '', mode.raw_user || ''].join('\n');
    const checks = [
      { pattern: /STRUCTURAL RULES:/i, weight: 2 },
      { pattern: /FORMAT RULES:/i, weight: 2 },
      { pattern: /QUALITY RULES:/i, weight: 2 },
      { pattern: /CHARACTER RULES:/i, weight: 1 },
      { pattern: /\bMUST\b/i, weight: 1 },
      { pattern: /\bEXACTLY\b/i, weight: 1 },
      { pattern: /Do NOT/i, weight: 1 },
      { pattern: /<think>/i, weight: 1 },
      { pattern: /<outline>/i, weight: 1 },
      { pattern: /\[TURNING_POINT\]/i, weight: 1 },
    ];
    const score = checks.reduce(function (total, item) {
      return total + (item.pattern.test(text) ? item.weight : 0);
    }, 0);
    if (score >= 7) return '高';
    if (score >= 3) return '中';
    return '低';
  }

  function renderPromptPanel(data) {
    const switchNode = byId('prompt_mode_switch');
    const modes = (((data || {}).preview || {}).modes) || [];
    if (!modes.length) {
      switchNode.innerHTML = '<div class="message">目前沒有可顯示的 prompt mode。</div>';
      byId('prompt_analysis_stats').innerHTML = '';
      const capNode = byId('prompt_capability_chips');
      if (capNode) capNode.innerHTML = '';
      const varNode = byId('prompt_variable_chips');
      if (varNode) varNode.innerHTML = '';
      byId('prompt_analysis_notes').innerHTML = '';
      byId('prompt_template_path').textContent = '-';
      byId('prompt_raw_system').textContent = '';
      byId('prompt_raw_user').textContent = '';
      byId('prompt_filled_system').textContent = '';
      byId('prompt_filled_user').textContent = '';
      return;
    }

    const activeMode = modes.find(function (mode) {
      return String(mode.id) === String(state.activePromptMode);
    }) || modes[0];
    state.activePromptMode = String(activeMode.id || 'g0');

    switchNode.innerHTML = modes.map(function (mode) {
      const modeId = String(mode.id || '');
      const isActive = modeId === state.activePromptMode;
      return (
        '<button class="prompt-mode-btn ' + (isActive ? 'active ' : '') + escapeHtml(modeId) + '" data-prompt-mode="' + escapeHtml(modeId) + '" type="button">' +
          '<span class="prompt-mode-id">' + escapeHtml(modeId.toUpperCase()) + '</span>' +
          '<span class="prompt-mode-copy">' +
            '<strong>' + escapeHtml(mode.label || modeId) + '</strong>' +
            '<small>' + escapeHtml(mode.description || '') + '</small>' +
            capabilityDotsHtml(modeId) +
          '</span>' +
        '</button>'
      );
    }).join('');

    switchNode.querySelectorAll('[data-prompt-mode]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.activePromptMode = button.getAttribute('data-prompt-mode') || 'g0';
        renderPromptPanel(state.previewData || {});
      });
    });

    const rawPlaceholders = uniqueStrings(
      extractPlaceholders(activeMode.raw_system).concat(extractPlaceholders(activeMode.raw_user))
    );
    const signals = promptSignalsForMode(activeMode);
    const notes = promptNotesForMode(activeMode);
    const filledLength = String((activeMode.filled_system || '') + (activeMode.filled_user || '')).length;

    byId('prompt_analysis_stats').innerHTML = [
      ['模式', activeMode.id ? String(activeMode.id).toUpperCase() : '-'],
      ['控制層級', controlLevelForMode(activeMode)],
      ['輸入變數', rawPlaceholders.length || 0],
      ['結構約束', structuralConstraintLevel(activeMode)],
      ['填入後字數', filledLength || 0],
    ].map(function (pair) {
      return '<div class="mini"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
    }).join('');

    const capabilityNode = byId('prompt_capability_chips');
    if (capabilityNode) {
      capabilityNode.innerHTML = signals.map(function (label) {
        return '<span class="chip chip-capability">' + escapeHtml(label) + '</span>';
      }).join('') || '<span class="chip chip-muted">無額外能力標記</span>';
    }

    const variableNode = byId('prompt_variable_chips');
    if (variableNode) {
      variableNode.innerHTML = rawPlaceholders.map(function (token) {
        return '<span class="chip chip-variable">' + escapeHtml(token) + '</span>';
      }).join('') || '<span class="chip chip-muted">模板沒有輸入變數</span>';
    }

    byId('prompt_analysis_notes').innerHTML = notes.map(function (note) {
      return '<div class="bullet-item">' + escapeHtml(note) + '</div>';
    }).join('');

    byId('prompt_template_path').textContent = activeMode.template_path || '-';
    byId('prompt_raw_system').innerHTML = highlightPlaceholders(activeMode.raw_system || '');
    byId('prompt_raw_user').innerHTML = highlightPlaceholders(activeMode.raw_user || '');
    byId('prompt_filled_system').textContent = activeMode.filled_system || '';
    byId('prompt_filled_user').textContent = activeMode.filled_user || '';
  }

  function renderKgStats(profile) {
    const node = byId('kg_stats_grid');
    if (!node) return;
    const graph = (profile && profile.focused_graph) || {};
    const stats = [
      ['KG 節點', Array.isArray(graph.nodes) ? graph.nodes.length : 0],
      ['KG 邊', Array.isArray(graph.edges) ? graph.edges.length : 0],
      ['角色', Array.isArray(profile.characters) ? profile.characters.length : 0],
      ['場景', Array.isArray(profile.scenes) ? profile.scenes.length : 0],
      ['變體', Object.keys(profile.selected_variations || {}).length],
      ['分支', Array.isArray(profile.branch_slots) ? profile.branch_slots.length : 0],
      ['互動點', Array.isArray(profile.interaction_plan) ? profile.interaction_plan.length : 0],
    ];
    node.innerHTML = stats.map(function (pair) {
      return '<div class="mini"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
    }).join('');
  }

  function renderProfile(data) {
    const profile = (data || {}).profile || {};
    renderKgStats(profile);
    const profileSummary = byId('profile_summary');
    if (profileSummary) {
      profileSummary.innerHTML = [
        ['年齡', profile.age_label || '-'],
        ['類別', profile.category_label || '-'],
        ['子類別', profile.subcategory_label || '-'],
        ['主題', profile.theme_label || '-'],
        ['預期頁數', profile.pages_expected || '-'],
        ['Visual Style', profile.visual_style || '-'],
      ].map(function (pair) {
        var w = (pair[0] === 'Visual Style') ? ' wide' : '';
        return '<div class="mini' + w + '"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
      }).join('');
    }

    const chips = [];
    (profile.characters || []).forEach(function (item) {
      chips.push('<span class="chip">角色: ' + escapeHtml(item) + '</span>');
    });
    (profile.scenes || []).forEach(function (item) {
      chips.push('<span class="chip">場景: ' + escapeHtml(item) + '</span>');
    });
    if (profile.moral) chips.push('<span class="chip">Moral: ' + escapeHtml(profile.moral) + '</span>');
    byId('kg_lists').innerHTML = chips.join('') || '<span class="chip">沒有資料</span>';

    byId('variation_json').textContent = JSON.stringify({
      selected_variations: profile.selected_variations || {},
      branch_slots: profile.branch_slots || [],
    }, null, 2);
    byId('prompt_guidelines').textContent = profile.prompt_guidelines || '';
    byId('effective_guidelines').textContent = profile.effective_guidelines || '';
    byId('user_intent_json').textContent = JSON.stringify(profile.user_intent || {}, null, 2);
    byId('interaction_plan_json').textContent = JSON.stringify(profile.interaction_plan || [], null, 2);
    renderFocusedKg(profile.focused_graph || null);
  }

  function labelForGroup(groupKey) {
    return {
      selection: 'Selection',
      character: '角色',
      scene: '場景',
      concept: '概念',
      emotion: '情緒',
      objective: '教學目標',
      variation: '變體',
      branch: '分支',
      default: '其他',
    }[groupKey] || String(groupKey || '其他');
  }

  function labelForKind(kind) {
    return {
      age_group: 'age',
      category: 'category',
      subcategory: 'subcategory',
      theme: 'theme',
      character: 'character',
      scene: 'scene',
      concept: 'concept',
      emotion: 'emotion',
      learning_objective: 'objective',
      generation_param: 'generation control',
      branch_slot: 'branch',
    }[kind] || String(kind || 'node');
  }

  function groupNodesByKey(nodes) {
    const groups = {};
    (nodes || []).forEach(function (node) {
      const key = String(node.group || 'default');
      if (!groups[key]) groups[key] = [];
      groups[key].push(node);
    });
    return groups;
  }

  function renderSimpleNode(node, extraClass) {
    return (
      '<div class="kg-simple-node ' + escapeHtml(extraClass || '') + '">' +
        '<div class="kg-simple-title">' + escapeHtml(node.label || '') + '</div>' +
        '<div class="kg-simple-meta">' +
          '<span class="kg-simple-pill">' + escapeHtml(labelForKind(node.kind || '')) + '</span>' +
          (node.detail ? '<span class="kg-simple-pill muted">' + escapeHtml(node.detail) + '</span>' : '') +
        '</div>' +
      '</div>'
    );
  }

  function renderGroupBoard(targetId, groupedNodes, emptyMessage) {
    const node = byId(targetId);
    const keys = Object.keys(groupedNodes || {});
    if (!keys.length) {
      node.innerHTML = '<div class="message">' + escapeHtml(emptyMessage) + '</div>';
      return;
    }
    node.innerHTML = keys.map(function (groupKey) {
      return (
        '<section class="kg-cluster-card">' +
          '<div class="kg-cluster-title">' + escapeHtml(labelForGroup(groupKey)) + '</div>' +
          '<div class="kg-cluster-body">' +
            groupedNodes[groupKey].map(function (nodeItem) {
              return renderSimpleNode(nodeItem, 'group-' + groupKey);
            }).join('') +
          '</div>' +
        '</section>'
      );
    }).join('');
  }

  function renderFocusedKg(graph) {
    state.focusedGraph = graph || null;
    const pathSummaryNode = byId('kg_path_summary');
    const selectionNode = byId('kg_selection_cards');
    const supportNode = byId('kg_support_groups');
    const controlNode = byId('kg_control_groups');
    if (!graph || !Array.isArray(graph.nodes) || !graph.nodes.length) {
      pathSummaryNode.innerHTML = '<div class="message">目前沒有可展示的 KG 路徑。</div>';
      selectionNode.innerHTML = '';
      supportNode.innerHTML = '';
      controlNode.innerHTML = '';
      return;
    }

    const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
    const selectionOrder = {
      age_group: 1,
      category: 2,
      subcategory: 3,
      theme: 4,
    };
    const selectionPath = nodes.filter(function (node) {
      return node.lane === 'input' || node.lane === 'selection';
    }).slice().sort(function (a, b) {
      return (selectionOrder[a.kind] || 99) - (selectionOrder[b.kind] || 99);
    });

    pathSummaryNode.innerHTML = selectionPath.map(function (node, index) {
      const kind = String(node.kind || '').toLowerCase();
      return (
        '<div class="kg-path-step kind-' + escapeHtml(kind) + '">' +
          '<div class="kg-path-index">' + String(index + 1) + '</div>' +
          '<div class="kg-path-body">' +
            '<div class="kg-path-label">' + escapeHtml(labelForKind(node.kind || '')) + '</div>' +
            '<div class="kg-path-value">' + escapeHtml(node.label || '') + '</div>' +
          '</div>' +
          (index < selectionPath.length - 1 ? '<div class="kg-path-arrow">→</div>' : '') +
        '</div>'
      );
    }).join('') || '<div class="message">目前沒有選擇路徑資料。</div>';

    selectionNode.innerHTML = selectionPath.map(function (node) {
      return renderSimpleNode(node, 'selection');
    }).join('') || '<div class="message">目前沒有選擇節點。</div>';

    renderGroupBoard(
      'kg_support_groups',
      groupNodesByKey(nodes.filter(function (node) { return node.lane === 'knowledge'; })),
      '目前沒有知識支撐節點。'
    );
    renderGroupBoard(
      'kg_control_groups',
      groupNodesByKey(nodes.filter(function (node) { return node.lane === 'control'; })),
      '目前沒有生成控制節點。'
    );
  }

  function drawFocusedKgEdges() {
    return;
  }

  const CONTROL_FLOW_STEPS = [
    {id: 'assemble', label: 'Prompt Assemble', detail: '帶入 KG + Control 模板'},
    {id: 'generate', label: 'Model Generate', detail: '語言模型輸出草稿'},
    {id: 'validate', label: 'Structural Validate', detail: '檢查章節 / 格式 / 狀態'},
    {id: 'repair', label: 'Retry or Repair', detail: '失敗時帶 feedback 修正'},
    {id: 'persist', label: 'Persist Output', detail: '寫入 story root 與證據'},
  ];

  function renderControlFlow(data, evidenceData) {
    const node = byId('control_flow');
    if (!node) return;
    const retry = ((data || {}).preview || {}).retry_summary || {};
    const retryAttempts = ((evidenceData || {}).retry || {}).retry_attempts || 0;
    const validationFailures = ((evidenceData || {}).retry || {}).validation_failures || 0;
    const badges = {
      assemble: '模式: ' + (((data || {}).preview || {}).preview_step || '-'),
      generate: '控制點 ' + (Array.isArray(retry.controls) ? retry.controls.length : 0) + ' 項',
      validate: 'Fail ' + validationFailures + ' 次',
      repair: 'Retry 上限 ' + (retry.configured_max_retries || 0),
      persist: '觀察到 Retry ' + retryAttempts + ' 次',
    };
    node.innerHTML = CONTROL_FLOW_STEPS.map(function (step, index) {
      const arrow = index < CONTROL_FLOW_STEPS.length - 1 ? '<div class="control-flow-arrow">→</div>' : '';
      return (
        '<div class="control-flow-step step-' + escapeHtml(step.id) + '">' +
          '<div class="control-flow-index">' + String(index + 1) + '</div>' +
          '<div class="control-flow-body">' +
            '<div class="control-flow-label">' + escapeHtml(step.label) + '</div>' +
            '<div class="control-flow-sub">' + escapeHtml(step.detail) + '</div>' +
            '<div class="control-flow-badge">' + escapeHtml(badges[step.id] || '') + '</div>' +
          '</div>' +
        '</div>' + arrow
      );
    }).join('');
  }

  function renderRetry(data) {
    renderControlProof(data, state.evidenceData);
    renderControlFlow(data, state.evidenceData);
    const preview = (data || {}).preview || {};
    const retry = preview.retry_summary || {};
    const pageStructure = preview.page_structure || {};
    const phase = pageStructure.page_function || pageStructure.phase || '-';
    byId('retry_summary').innerHTML = [
      ['展示階段', preview.preview_step || '-'],
      ['展示頁碼', preview.preview_page || '-'],
      ['頁面功能', phase],
      ['重試上限', retry.configured_max_retries || 0],
      ['控制點數', Array.isArray(retry.controls) ? retry.controls.length : 0],
    ].map(function (pair) {
      return '<div class="mini"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
    }).join('');
    byId('page_structure_json').textContent = JSON.stringify(preview.page_structure || {}, null, 2);
    byId('visual_context_json').textContent = JSON.stringify(preview.visual_context || {}, null, 2);
    byId('retry_guidance_text').textContent = retry.sample_retry_feedback || '';
    byId('retry_controls').innerHTML = (retry.controls || []).map(function (item) {
      return '<div class="bullet-item">' + escapeHtml(item) + '</div>';
    }).join('') || '<div class="message">目前沒有控制點資料。</div>';
  }

  function renderEvidenceStats(data) {
    const node = byId('evidence_stats_grid');
    if (!node) return;
    const files = (data && data.files) || {};
    const promptFiles = (data && data.prompt_files) || {};
    const retry = (data && data.retry) || {};
    const stats = [
      ['核心檔案', Object.keys(files).length],
      ['Page Prompts', Array.isArray(promptFiles.page_prompts) ? promptFiles.page_prompts.length : 0],
      ['Character Prompts', Array.isArray(promptFiles.character_prompts) ? promptFiles.character_prompts.length : 0],
      ['Retry 事件', Array.isArray(retry.recent_events) ? retry.recent_events.length : 0],
    ];
    node.innerHTML = stats.map(function (pair) {
      return '<div class="mini"><span>' + escapeHtml(pair[0]) + '</span><strong>' + escapeHtml(pair[1]) + '</strong></div>';
    }).join('');
  }

  function renderEvidence(data) {
    if (!data || data.ok === false) {
      byId('evidence_story_root').textContent = '-';
      byId('evidence_resource_dir').textContent = '-';
      byId('evidence_retry_count').textContent = '0';
      byId('evidence_validation_failures').textContent = '0';
      byId('evidence_files').innerHTML = '<div class="message">找不到可展示的 story evidence。</div>';
      byId('page_prompt_list').innerHTML = '<div class="message">目前沒有 page prompt 檔案。</div>';
      byId('character_prompt_list').innerHTML = '<div class="message">目前沒有角色 prompt 檔案。</div>';
      byId('retry_event_list').innerHTML = '<div class="message">目前沒有 retry / validation 事件。</div>';
      renderEvidenceStats(null);
      renderOverview();
      return;
    }
    renderEvidenceStats(data);

    byId('evidence_story_root').textContent = data.story_root || '-';
    byId('evidence_resource_dir').textContent = data.resource_dir || '-';
    byId('evidence_retry_count').textContent = String((data.retry || {}).retry_attempts || 0);
    byId('evidence_validation_failures').textContent = String((data.retry || {}).validation_failures || 0);

    const files = data.files || {};
    const evidenceKindMap = {
      outline: {label: 'Outline', klass: 'kind-outline'},
      plan: {label: 'Story Plan', klass: 'kind-plan'},
      story_plan: {label: 'Story Plan', klass: 'kind-plan'},
      story: {label: 'Story Text', klass: 'kind-story'},
      story_text: {label: 'Story Text', klass: 'kind-story'},
      narration: {label: 'Narration', klass: 'kind-narration'},
      dialogue: {label: 'Dialogue', klass: 'kind-dialogue'},
      character: {label: 'Character', klass: 'kind-character'},
      characters: {label: 'Character', klass: 'kind-character'},
      scene: {label: 'Scene', klass: 'kind-scene'},
      scenes: {label: 'Scene', klass: 'kind-scene'},
      cover: {label: 'Cover', klass: 'kind-cover'},
      title: {label: 'Title', klass: 'kind-title'},
      meta: {label: 'Meta', klass: 'kind-meta'},
    };
    function evidenceKind(key) {
      const token = String(key || '').toLowerCase();
      if (evidenceKindMap[token]) return evidenceKindMap[token];
      for (const prefix in evidenceKindMap) {
        if (token.indexOf(prefix) === 0) return evidenceKindMap[prefix];
      }
      return {label: 'Evidence', klass: 'kind-default'};
    }
    byId('evidence_files').innerHTML = Object.keys(files).map(function (key) {
      const item = files[key] || {};
      const kind = evidenceKind(key);
      return (
        '<div class="stack-item evidence-card ' + escapeHtml(kind.klass) + '">' +
          '<div class="evidence-card-head">' +
            '<span class="evidence-kind-badge">' + escapeHtml(kind.label) + '</span>' +
            '<h4>' + escapeHtml(key) + '</h4>' +
          '</div>' +
          '<div class="mode-path">' + escapeHtml(item.path || '-') + '</div>' +
          '<pre class="console light">' + escapeHtml(item.excerpt || '') + '</pre>' +
        '</div>'
      );
    }).join('') || '<div class="message">目前沒有核心輸出檔案。</div>';

    byId('page_prompt_list').innerHTML = ((data.prompt_files || {}).page_prompts || []).map(function (item) {
      return (
        '<div class="stack-item">' +
          '<h4>Page ' + escapeHtml(item.page) + '</h4>' +
          '<div class="mode-path">' + escapeHtml(item.path || '') + '</div>' +
          '<pre class="console light">' + escapeHtml(item.excerpt || '') + '</pre>' +
        '</div>'
      );
    }).join('') || '<div class="message">目前沒有 page prompt 檔案。</div>';

    byId('character_prompt_list').innerHTML = ((data.prompt_files || {}).character_prompts || []).map(function (item) {
      return (
        '<div class="stack-item">' +
          '<h4>' + escapeHtml(item.name || '') + '</h4>' +
          '<div class="mode-path">' + escapeHtml(item.path || '') + '</div>' +
          '<pre class="console light">' + escapeHtml(item.excerpt || '') + '</pre>' +
        '</div>'
      );
    }).join('') || '<div class="message">目前沒有角色 prompt 檔案。</div>';

    byId('retry_event_list').innerHTML = ((data.retry || {}).recent_events || []).map(function (item) {
      const level = String(item.level || 'info').toLowerCase();
      return (
        '<div class="event-item ' + escapeHtml(level) + '">' +
          '<div class="event-meta">' + escapeHtml((item.timestamp || '-') + ' | ' + level) + '</div>' +
          '<div>' + escapeHtml(item.message || '') + '</div>' +
        '</div>'
      );
    }).join('') || '<div class="message">目前沒有 retry / validation 事件。</div>';

    if (state.previewData) {
      renderControlFlow(state.previewData, data);
      renderControlProof(state.previewData, data);
    }
    renderOverview();
  }

  async function refreshPreview() {
    byId('preview_status').textContent = '載入 preview 中...';
    try {
      const data = await apiPost('/api/demo/generation-preview', collectFormData());
      state.previewData = data;
      renderPromptPanel(data);
      renderProfile(data);
      renderRetry(data);
      renderOverview();
      byId('preview_status').textContent = 'Preview 已更新，請切換到對應視圖進行展示。';
    } catch (err) {
      byId('preview_status').textContent = String((err && err.message) || err || 'Preview 載入失敗。');
    }
  }

  async function refreshEvidence() {
    byId('evidence_status').textContent = '載入 story evidence 中...';
    const hint = encodeURIComponent((byId('story_root_hint').value || '').trim());
    try {
      const data = await apiGet('/api/demo/story-evidence?story_root=' + hint);
      state.evidenceData = data;
      renderEvidence(data);
      byId('evidence_status').textContent = '已載入最新 story evidence。';
    } catch (err) {
      state.evidenceData = null;
      renderEvidence(null);
      byId('evidence_status').textContent = String((err && err.message) || err || 'Evidence 載入失敗。');
    }
  }

  async function init() {
    byId('btn_apply_saved_template').addEventListener('click', applySelectedTemplate);
    byId('btn_refresh_preview').addEventListener('click', refreshPreview);
    byId('btn_refresh_evidence').addEventListener('click', refreshEvidence);
    byId('btn_presentation_mode').addEventListener('click', function () {
      setPresentationMode(!state.presentationMode);
    });
    document.querySelectorAll('[data-demo-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        switchView(button.getAttribute('data-demo-view') || 'overview');
      });
    });

    try {
      const templates = await apiGet('/api/templates');
      renderTemplates(templates);
    } catch (_err) {
      renderTemplates([]);
    }

    switchView('overview');
    renderControlMatrix();
    renderResearchClaims();
    renderPipelineFlow();
    renderDefenseScript();
    renderControlProof(null, null);
    renderControlFlow(null, null);
    renderEvidenceStats(null);
    renderKgStats({});
    await refreshPreview();
    await refreshEvidence();
  }

  init();
})();

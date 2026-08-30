const fullAboutText = `I'm Mihir Lakhani, a B.Tech Computer Science and Engineering student specializing in Computer Networking at SRM Institute of Science and Technology, Kattankulathur. I am building toward full-stack AI/ML engineering and AI/ML engineering roles while learning practical MLOps: how to deploy, operate, secure, and optimize AI applications. My ML journey started with a college project and deepened when I built a cardiovascular decision-tree project without machine-learning libraries; working through entropy, information gain, splits, and predictions made the fundamentals click. Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow by Aurelien Geron helped build a practical foundation for later work. As an AI/ML Research Intern on a Network Digital Twin Project, I explored 6G-oriented digital twins, SLA-breach prediction, explainability, and proactive network-control ideas. That work led to the Closed Loop SLA Violation Simulation, which received third place at Nokia Campus Connect 2025, and gave me the foundation to build the Fleet Smart Vehicle Digital Twin Prototype. I now focus on turning ML experimentation into usable systems with Python, Flask, React, source-cited RAG, and practical engineering habits. Outside technical work, I enjoy story-driven games when I have actual free time, although recent months have been mostly coursework, research, and projects.`;

let aboutTypingTimer = null;
let aboutTypingRun = 0;

function stopAboutTyping(cursor) {
  aboutTypingRun += 1;

  if (aboutTypingTimer !== null) {
    window.clearTimeout(aboutTypingTimer);
    aboutTypingTimer = null;
  }

  cursor.style.display = "none";
}

function typeParagraphWithMovingCursor(text, element, cursor, speed = 18) {
  stopAboutTyping(cursor);
  const currentRun = ++aboutTypingRun;

  element.replaceChildren();
  cursor.style.display = "inline-block";
  cursor.style.fontSize = "4em";
  cursor.style.color = "white";
  cursor.classList.add("blinking-cursor");

  let i = 0;
  const typingCaret = document.createElement("span");

  typingCaret.id = "type-cursor-inner";
  typingCaret.className = "blinking-cursor";
  typingCaret.style.fontSize = "1.6em";
  typingCaret.style.color = "white";
  typingCaret.style.display = "inline-block";
  typingCaret.style.width = "0.6em";
  typingCaret.textContent = "|";

  function type() {
    if (currentRun !== aboutTypingRun || element.classList.contains("hidden")) {
      return;
    }

    if (i <= text.length) {
      element.replaceChildren(document.createTextNode(text.slice(0, i)), typingCaret);
      i++;
      aboutTypingTimer = window.setTimeout(type, speed);
    } else {
      element.textContent = text;
      cursor.style.display = "none";
      aboutTypingTimer = null;
    }
  }

  type();
}

function toggleParagraph() {
  const para = document.getElementById("about-paragraph");
  const cursor = document.getElementById("type-cursor");
  if (para) {
    if (para.classList.contains("hidden")) {
      para.classList.remove("hidden");
      typeParagraphWithMovingCursor(fullAboutText, para, cursor, 18);
    } else {
      stopAboutTyping(cursor);
      para.classList.add("hidden");
      para.replaceChildren();
    }
  }
}

const taglineText = "THIS PORTFOLIO IS A RECORD OF THE PROJECTS I HAVE WORKED ON WHILE LEARNING MACHINE LEARNING, AI SYSTEMS, AND SOFTWARE DEVELOPMENT.";
const taglineElem = document.getElementById("tagline");

function typeTagline(text, elem, speed = 50) {
  let i = 0;
  function type() {
    if (i <= text.length) {
      elem.innerHTML = text.slice(0, i) + '<span class="blink-caret">|</span>';
      i++;
      setTimeout(type, speed);
    } else {
      // Remove caret after typing completes
      elem.innerHTML = text + '<span class="blink-caret">|</span>';
    }
  }
  type();
}

// Start typing effect
typeTagline(taglineText, taglineElem);

function ensureSocialDock() {
  if (document.querySelector('.social-dock')) return;

  const profiles = [
    {
      label: 'Linked_',
      emphasis: 'In',
      href: 'https://www.linkedin.com/in/mihir-lakhani-149504327/',
      icon: '/static/images/lkd.png'
    },
    {
      label: 'Git_',
      emphasis: 'Hub',
      href: 'https://github.com/Mihir-Lakhani',
      icon: '/static/images/github-dock.png'
    }
  ];
  const dock = document.createElement('aside');

  dock.className = 'social-dock';
  dock.setAttribute('aria-label', 'Professional profiles');

  profiles.forEach(profile => {
    const link = document.createElement('a');
    const icon = document.createElement('img');
    const label = document.createElement('span');
    const emphasis = document.createElement('em');

    link.href = profile.href;
    link.target = '_blank';
    link.rel = 'noopener';
    icon.src = profile.icon;
    icon.alt = '';
    icon.setAttribute('aria-hidden', 'true');
    label.append(profile.label);
    emphasis.textContent = profile.emphasis;
    label.append(emphasis);
    link.append(icon, label);
    dock.append(link);
  });

  document.body.append(dock);
}

ensureSocialDock();

function renderAboutHighlights() {
  const highlights = [
    'B.Tech Computer Science and Engineering student specializing in Computer Networking at SRMIST, building toward full-stack AI/ML engineering.',
    'AI/ML Research Intern on a Network Digital Twin Project, exploring 6G-oriented digital twins, SLA-breach prediction, explainability, and proactive network-control ideas.',
    'Presented the research work at Nokia Campus Connect 2025, earning third place, and earned first place in a section-level AutoCAD competition.',
    'Built the Source-Cited RAG Assistant to make approved portfolio material easier to explore with validated citations and approved diagrams.',
    'Growing practical MLOps skills alongside Python, Flask, React, data visualization, model evaluation, and explainable ML work.'
  ];
  const list = document.querySelector('.lux-list');

  if (!list) return;

  list.replaceChildren(...highlights.map(highlight => {
    const item = document.createElement('li');
    const statement = document.createElement('strong');

    statement.textContent = highlight;
    item.append(statement);
    return item;
  }));
}

renderAboutHighlights();

function createPortfolioAssistantPanel(panel) {
  panel.replaceChildren();
  panel.setAttribute('aria-labelledby', 'aboutChatStatus');

  const header = document.createElement('div');
  header.className = 'about-chat-header';

  const status = document.createElement('p');
  status.className = 'about-chat-status';
  status.id = 'aboutChatStatus';
  status.textContent = 'Ask About Me';

  const detail = document.createElement('p');
  detail.className = 'about-chat-detail';
  detail.textContent = 'Portfolio answers cite approved public sources. General conversation is clearly labelled.';

  header.append(status, detail, createAboutChatWindowControls());

  const transcript = document.createElement('div');
  transcript.className = 'about-chat-transcript';
  transcript.id = 'aboutChatTranscript';
  transcript.setAttribute('role', 'log');
  transcript.setAttribute('aria-live', 'polite');
  transcript.setAttribute('aria-relevant', 'additions text');

  const emptyMessage = document.createElement('p');
  emptyMessage.className = 'about-chat-empty';
  emptyMessage.textContent = 'Try asking about a project, skill, certification, or learning journey.';
  transcript.append(emptyMessage);

  const form = document.createElement('form');
  form.className = 'about-chat-form';
  form.id = 'aboutChatForm';

  const label = document.createElement('label');
  label.className = 'visually-hidden';
  label.htmlFor = 'aboutChatQuestion';
  label.textContent = "Ask a question about Mihir's public work";

  const question = document.createElement('textarea');
  question.id = 'aboutChatQuestion';
  question.name = 'question';
  question.rows = 2;
  question.maxLength = 2000;
  question.required = true;
  question.placeholder = 'Ask about a project, skill, or certification...';

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.append('Ask ');
  const arrow = document.createElement('span');
  arrow.setAttribute('aria-hidden', 'true');
  arrow.textContent = '↗';
  submit.append(arrow);

  const feedback = document.createElement('p');
  feedback.className = 'about-chat-feedback';
  feedback.id = 'aboutChatFeedback';
  feedback.setAttribute('aria-live', 'polite');

  const footer = document.createElement('div');
  footer.className = 'about-chat-form-footer';
  footer.append(feedback, submit);

  form.append(label, question, footer);
  panel.append(header, transcript, form);
  return { transcript, form, question, submit, feedback };
}

function createAboutChatMaximizeButton() {
  const maximize = document.createElement('button');
  maximize.className = 'about-chat-maximize';
  maximize.type = 'button';
  maximize.setAttribute('aria-label', 'Maximize Ask About Me');
  maximize.setAttribute('aria-pressed', 'false');
  maximize.title = 'Maximize assistant';

  const maximizeIcon = document.createElement('span');
  maximizeIcon.className = 'about-chat-maximize-icon';
  maximizeIcon.setAttribute('aria-hidden', 'true');
  maximize.append(maximizeIcon);
  return maximize;
}

function createAboutChatCloseButton() {
  const close = document.createElement('button');
  close.className = 'about-chat-close';
  close.type = 'button';
  close.setAttribute('aria-label', 'Close Ask About Me');
  close.title = 'Close assistant';
  close.textContent = '×';
  return close;
}

function createAboutChatWindowControls() {
  const controls = document.createElement('div');
  controls.className = 'about-chat-window-controls';
  controls.setAttribute('aria-label', 'Assistant window controls');

  controls.append(createAboutChatMaximizeButton(), createAboutChatCloseButton());
  return controls;
}

function ensureAboutChatWindowControls(panel) {
  const header = panel.querySelector('.about-chat-header');
  if (!header) return { close: null, maximize: null };

  let controls = header.querySelector('.about-chat-window-controls');
  if (!controls) {
    controls = document.createElement('div');
    controls.className = 'about-chat-window-controls';
    controls.setAttribute('aria-label', 'Assistant window controls');
    header.append(controls);
  }

  let maximize = header.querySelector('.about-chat-maximize');
  if (!maximize) {
    maximize = createAboutChatMaximizeButton();
  }
  if (maximize.parentElement !== controls) controls.prepend(maximize);

  let close = header.querySelector('.about-chat-close');
  if (!close) {
    close = createAboutChatCloseButton();
  }

  if (close.parentElement !== controls) controls.append(close);
  return { close, maximize };
}

function ensureAboutChatBackdrop() {
  let backdrop = document.getElementById('aboutChatBackdrop');
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.id = 'aboutChatBackdrop';
    backdrop.className = 'about-chat-backdrop';
    backdrop.hidden = true;
    backdrop.setAttribute('aria-hidden', 'true');
  }

  if (backdrop.parentElement !== document.body) document.body.append(backdrop);
  return backdrop;
}

const ABOUT_CHAT_MOTION = Object.freeze({
  duration: 240,
  easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
});

let aboutChatPanelAnimation = null;
let aboutChatBackdropAnimation = null;
let aboutChatMotionVersion = 0;
let activeAboutChatVisualFocus = null;

function prefersReducedAboutChatMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

function clearAboutChatAnimation(animation, target) {
  if (!animation) return;

  if (target === 'panel' && aboutChatPanelAnimation === animation) {
    aboutChatPanelAnimation = null;
  }
  if (target === 'backdrop' && aboutChatBackdropAnimation === animation) {
    aboutChatBackdropAnimation = null;
  }
  animation.cancel();
}

function cancelAboutChatMotion() {
  aboutChatMotionVersion += 1;
  clearAboutChatAnimation(aboutChatPanelAnimation, 'panel');
  clearAboutChatAnimation(aboutChatBackdropAnimation, 'backdrop');
  return aboutChatMotionVersion;
}

function createAboutChatCssAnimation(element, keyframes) {
  const [from = {}, to = {}] = keyframes;
  const properties = [...new Set([...Object.keys(from), ...Object.keys(to)])];
  const initialValues = Object.fromEntries(
    properties.map(property => [property, element.style[property]])
  );
  const transitionProperties = properties
    .filter(property => property !== 'transformOrigin')
    .map(property => property.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`));
  const initialTransition = element.style.transition;
  let settled = false;
  let timeoutId = null;
  let resolveFinished = null;

  const cleanupListeners = () => {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    element.removeEventListener('transitionend', finish);
  };
  const finish = event => {
    if (event && event.target !== element) return;
    if (settled) return;
    settled = true;
    cleanupListeners();
    resolveFinished?.();
  };
  const restoreInitialStyles = () => {
    element.style.transition = initialTransition;
    Object.entries(initialValues).forEach(([property, value]) => {
      element.style[property] = value;
    });
  };
  const finished = new Promise(resolve => {
    resolveFinished = resolve;
  });

  element.style.transition = 'none';
  Object.assign(element.style, from);
  void element.offsetWidth;
  element.style.transition = transitionProperties
    .map(property => `${property} ${ABOUT_CHAT_MOTION.duration}ms ${ABOUT_CHAT_MOTION.easing}`)
    .join(', ');
  Object.assign(element.style, to);
  element.addEventListener('transitionend', finish);
  timeoutId = window.setTimeout(finish, ABOUT_CHAT_MOTION.duration + 80);

  return {
    finished,
    cancel() {
      finish();
      restoreInitialStyles();
    }
  };
}

function playAboutChatAnimation(element, keyframes, target) {
  if (prefersReducedAboutChatMotion()) {
    return null;
  }

  const animation = typeof element.animate === 'function'
    ? element.animate(keyframes, {
        duration: ABOUT_CHAT_MOTION.duration,
        easing: ABOUT_CHAT_MOTION.easing,
        fill: 'both'
      })
    : createAboutChatCssAnimation(element, keyframes);

  if (target === 'panel') {
    aboutChatPanelAnimation = animation;
  } else {
    aboutChatBackdropAnimation = animation;
  }
  return animation;
}

function waitForAboutChatAnimation(animation) {
  return animation?.finished.catch(() => undefined) ?? Promise.resolve();
}

function updateAboutChatWindowMaximizedState(panel, shouldMaximize) {
  const maximized = Boolean(shouldMaximize);
  panel.classList.toggle('is-maximized', maximized);
  panel.dataset.maximized = maximized ? 'true' : 'false';

  const { maximize } = ensureAboutChatWindowControls(panel);
  if (maximize) {
    maximize.setAttribute('aria-pressed', String(maximized));
    maximize.setAttribute('aria-label', maximized ? 'Restore Ask About Me' : 'Maximize Ask About Me');
    maximize.title = maximized ? 'Restore assistant' : 'Maximize assistant';
  }
}

function setAboutChatWindowMaximized(panel, shouldMaximize) {
  const maximized = Boolean(shouldMaximize);
  updateAboutChatWindowMaximizedState(panel, maximized);

  const active = maximized && !panel.hidden;
  ensureAboutChatBackdrop().hidden = !active;
  document.body.classList.toggle('about-chat-window-maximized', active);
}

function transitionAboutChatWindowMaximized(panel, shouldMaximize) {
  const maximized = Boolean(shouldMaximize);
  if (panel.classList.contains('is-maximized') === maximized) return;

  if (panel.hidden || prefersReducedAboutChatMotion()) {
    cancelAboutChatMotion();
    setAboutChatWindowMaximized(panel, maximized);
    return;
  }

  const motionVersion = cancelAboutChatMotion();
  const before = panel.getBoundingClientRect();
  const backdrop = ensureAboutChatBackdrop();

  if (maximized) {
    backdrop.hidden = false;
    document.body.classList.add('about-chat-window-maximized');
  }

  updateAboutChatWindowMaximizedState(panel, maximized);
  const after = panel.getBoundingClientRect();
  const translateX = before.left - after.left;
  const translateY = before.top - after.top;
  const scaleX = before.width / Math.max(after.width, 1);
  const scaleY = before.height / Math.max(after.height, 1);
  const panelAnimation = playAboutChatAnimation(
    panel,
    [
      {
        opacity: 1,
        transform: `translate3d(${translateX}px, ${translateY}px, 0) scale(${scaleX}, ${scaleY})`,
        transformOrigin: 'top left'
      },
      { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1, 1)', transformOrigin: 'top left' }
    ],
    'panel'
  );
  const backdropAnimation = playAboutChatAnimation(
    backdrop,
    maximized ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0 }],
    'backdrop'
  );

  void Promise.all([
    waitForAboutChatAnimation(panelAnimation),
    waitForAboutChatAnimation(backdropAnimation)
  ]).then(() => {
    if (motionVersion !== aboutChatMotionVersion) return;

    if (!maximized) backdrop.hidden = true;
    document.body.classList.toggle('about-chat-window-maximized', maximized && !panel.hidden);
    clearAboutChatAnimation(panelAnimation, 'panel');
    clearAboutChatAnimation(backdropAnimation, 'backdrop');
  });
}

function portfolioAssistantElements(panel) {
  const transcript = panel.querySelector('.about-chat-transcript');
  const form = panel.querySelector('.about-chat-form');
  const question = panel.querySelector('#aboutChatQuestion');
  const submit = form?.querySelector('button[type="submit"]');
  const feedback = panel.querySelector('.about-chat-feedback');

  if (!transcript || !form || !question || !submit || !feedback) {
    return createPortfolioAssistantPanel(panel);
  }

  // Upgrade a panel rendered by an older cached template without requiring a
  // server restart. The feedback and command always share one footer row.
  let footer = form.querySelector('.about-chat-form-footer');
  if (!footer) {
    footer = document.createElement('div');
    footer.className = 'about-chat-form-footer';
    form.append(footer);
  }
  if (feedback.parentElement !== footer || submit.parentElement !== footer) {
    footer.append(feedback, submit);
  }

  return { transcript, form, question, submit, feedback };
}

function safeCitationUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return null;

  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.origin === window.location.origin) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
    return parsed.protocol === 'https:' ? parsed.href : null;
  } catch {
    return null;
  }
}

function createAboutChatVisualButton(className, label, symbol, title) {
  const button = document.createElement('button');
  button.className = className;
  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.title = title;

  const icon = document.createElement('span');
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = symbol;
  button.append(icon);
  return button;
}

function restoreAboutChatVisualFocus(panel, shouldReturnFocus = true) {
  const active = activeAboutChatVisualFocus;
  if (!active || active.panel !== panel) return;

  active.placeholder.replaceWith(active.frame);
  active.frame.classList.remove('is-expanded');
  active.viewer.hidden = true;
  panel.classList.remove('is-visual-focus');
  activeAboutChatVisualFocus = null;

  if (shouldReturnFocus) {
    active.expandButton.focus({ preventScroll: true });
  }
}

function ensureAboutChatVisualFocus(panel) {
  let viewer = panel.querySelector('.about-chat-visual-focus');
  if (!viewer) {
    viewer = document.createElement('section');
    viewer.className = 'about-chat-visual-focus';
    viewer.hidden = true;
    viewer.setAttribute('aria-labelledby', 'aboutChatVisualFocusTitle');

    const header = document.createElement('div');
    header.className = 'about-chat-visual-focus-header';

    const title = document.createElement('p');
    title.className = 'about-chat-visual-focus-title';
    title.id = 'aboutChatVisualFocusTitle';

    const controls = document.createElement('div');
    controls.className = 'about-chat-visual-focus-controls';

    const restore = createAboutChatVisualButton(
      'about-chat-visual-restore',
      'Return visual to chat',
      '\u2921',
      'Return to chat'
    );
    const close = createAboutChatVisualButton(
      'about-chat-visual-close',
      'Close Ask About Me',
      '\u00d7',
      'Close assistant'
    );
    controls.append(restore, close);
    header.append(title, controls);

    const stage = document.createElement('div');
    stage.className = 'about-chat-visual-focus-stage';
    viewer.append(header, stage);
    panel.append(viewer);

    restore.addEventListener('click', () => restoreAboutChatVisualFocus(panel));
    close.addEventListener('click', () => {
      const toggle = document.getElementById('aboutChatToggle');
      restoreAboutChatVisualFocus(panel, false);
      if (toggle) setAboutChatLayerOpen(toggle, panel, false);
    });
  }

  return {
    viewer,
    title: viewer.querySelector('.about-chat-visual-focus-title'),
    stage: viewer.querySelector('.about-chat-visual-focus-stage')
  };
}

function openAboutChatVisualFocus(panel, frame, title, expandButton) {
  restoreAboutChatVisualFocus(panel, false);

  const { viewer, title: viewerTitle, stage } = ensureAboutChatVisualFocus(panel);
  const placeholder = document.createComment('about-chat-visual-anchor');
  frame.before(placeholder);
  stage.replaceChildren(frame);
  frame.classList.add('is-expanded');
  viewerTitle.textContent = title;
  viewer.hidden = false;
  panel.classList.add('is-visual-focus');

  activeAboutChatVisualFocus = {
    panel,
    viewer,
    frame,
    placeholder,
    expandButton
  };
}

function makeAboutChatVisualExpandable(panel, visual, title) {
  if (!panel || !visual || visual.parentElement?.classList.contains('about-chat-visual-frame')) {
    return;
  }

  const frame = document.createElement('div');
  frame.className = 'about-chat-visual-frame';
  visual.before(frame);
  frame.append(visual);

  const visualTitle = title?.trim() || 'Visual';
  const expand = createAboutChatVisualButton(
    'about-chat-visual-expand',
    `Expand ${visualTitle}`,
    '\u2922',
    'Expand visual'
  );
  frame.append(expand);
  expand.addEventListener('click', () => {
    openAboutChatVisualFocus(panel, frame, visualTitle, expand);
  });
}

function appendPortfolioChatMessage(
  transcript,
  role,
  text,
  citations = [],
  diagram = null,
  sections = [],
  diagrams = []
) {
  transcript.querySelector('.about-chat-empty')?.remove();
  const panel = transcript.closest('.about-chat-panel');

  const message = document.createElement('article');
  message.className = `about-chat-message about-chat-message-${role}`;

  const label = document.createElement('p');
  label.className = 'about-chat-message-label';
  label.textContent = role === 'visitor' ? 'You' : 'Portfolio assistant';

  const body = document.createElement('p');
  body.className = 'about-chat-message-text';
  body.textContent = text;
  message.append(label);

  const approvedSections = Array.isArray(sections)
    ? sections.filter(isApprovedPortfolioSection)
    : [];
  if (role === 'assistant' && approvedSections.length) {
    const sectionList = document.createElement('div');
    sectionList.className = 'about-chat-section-list';
    approvedSections.forEach(section => {
      const sectionBlock = document.createElement('section');
      sectionBlock.className = 'about-chat-section';

      const sectionTitle = document.createElement('h4');
      sectionTitle.className = 'about-chat-section-title';
      sectionTitle.textContent = section.title.trim();

      const sectionText = document.createElement('p');
      sectionText.className = 'about-chat-section-text';
      sectionText.textContent = section.text.trim();

      sectionBlock.append(sectionTitle, sectionText);
      sectionList.append(sectionBlock);
    });
    message.append(sectionList);
  } else {
    message.append(body);
  }

  if (role === 'assistant' && Array.isArray(citations) && citations.length) {
    const sources = document.createElement('div');
    sources.className = 'about-chat-sources';

    const sourceLabel = document.createElement('span');
    sourceLabel.className = 'about-chat-sources-label';
    sourceLabel.textContent = 'Sources';
    sources.append(sourceLabel);

    citations.forEach(citation => {
      if (!citation || typeof citation.title !== 'string') return;
      const href = safeCitationUrl(citation.url);
      const source = href ? document.createElement('a') : document.createElement('span');
      source.className = 'about-chat-source';
      source.textContent = citation.title;
      if (href && source instanceof HTMLAnchorElement) {
        source.href = href;
        if (href.startsWith('https://')) {
          source.target = '_blank';
          source.rel = 'noopener';
        }
      }
      sources.append(source);

      const demoHref = safeCitationUrl(citation.demo_url);
      if (demoHref && typeof citation.demo_label === 'string' && citation.demo_label.trim()) {
        const demo = document.createElement('a');
        demo.className = 'about-chat-source about-chat-source-demo';
        demo.textContent = citation.demo_label.trim();
        demo.href = demoHref;
        if (demoHref.startsWith('https://')) {
          demo.target = '_blank';
          demo.rel = 'noopener';
        }
        sources.append(demo);
      }
    });

    message.append(sources);
  }

  const approvedDiagrams = role === 'assistant'
    ? (Array.isArray(diagrams) ? diagrams : [])
        .filter(isApprovedPortfolioDiagram)
        .concat(isApprovedPortfolioDiagram(diagram) ? [diagram] : [])
        .filter((item, index, collection) =>
          collection.findIndex(candidate =>
            candidate.title === item.title && candidate.mermaid === item.mermaid
          ) === index
        )
    : [];
  approvedDiagrams.forEach(approvedDiagram => {
    const diagramBlock = document.createElement('section');
    diagramBlock.className = 'about-chat-diagram';

    const diagramTitle = document.createElement('p');
    diagramTitle.className = 'about-chat-diagram-title';
    diagramTitle.textContent = approvedDiagram.title;

    const diagramSurface = document.createElement('div');
    diagramSurface.className = 'about-chat-diagram-surface';
    diagramSurface.setAttribute('role', 'img');
    diagramSurface.setAttribute('aria-label', `${approvedDiagram.title} flowchart`);

    diagramBlock.append(diagramTitle, diagramSurface);
    makeAboutChatVisualExpandable(panel, diagramSurface, approvedDiagram.title);
    message.append(diagramBlock);
    void renderApprovedPortfolioDiagram(diagramSurface, approvedDiagram.mermaid);
  });

  message.querySelectorAll('img').forEach((image, index) => {
    makeAboutChatVisualExpandable(panel, image, image.alt || `Image ${index + 1}`);
  });

  transcript.append(message);
  transcript.scrollTop = transcript.scrollHeight;
}

function isApprovedPortfolioSection(section) {
  return Boolean(
    section &&
      typeof section === 'object' &&
      typeof section.title === 'string' &&
      typeof section.text === 'string' &&
      section.title.trim() &&
      section.text.trim()
  );
}

function isApprovedPortfolioDiagram(diagram) {
  return Boolean(
    diagram &&
      typeof diagram === 'object' &&
      typeof diagram.title === 'string' &&
      typeof diagram.mermaid === 'string' &&
      diagram.title.trim() &&
      diagram.mermaid.trim()
  );
}

async function renderApprovedPortfolioDiagram(surface, mermaidSource) {
  if (!window.mermaid?.render) {
    surface.textContent = 'Approved diagram could not be rendered in this browser.';
    return;
  }

  try {
    const renderId = `portfolio-diagram-${window.crypto?.randomUUID?.() || Date.now()}`;
    const rendered = await window.mermaid.render(renderId, mermaidSource);
    surface.replaceChildren();
    surface.insertAdjacentHTML('afterbegin', rendered.svg);
  } catch {
    surface.textContent = 'Approved diagram could not be rendered.';
  }
}

function createPortfolioConversationSessionId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  if (!window.crypto?.getRandomValues) return null;

  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function bindPortfolioAssistant(panel) {
  const { transcript, form, question, submit, feedback } = portfolioAssistantElements(panel);
  if (form.dataset.portfolioAssistantBound === 'true') return;

  form.dataset.portfolioAssistantBound = 'true';
  const conversationSessionId = createPortfolioConversationSessionId();
  let conversationEnded = false;

  function endPortfolioConversation() {
    if (!conversationSessionId || conversationEnded) return;
    conversationEnded = true;

    const body = JSON.stringify({ conversation_session_id: conversationSessionId });
    const beacon = new Blob([body], { type: 'application/json' });
    if (navigator.sendBeacon?.('/api/conversation/end', beacon)) return;

    fetch('/api/conversation/end', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true
    }).catch(() => {});
  }

  window.addEventListener('pagehide', endPortfolioConversation, { once: true });
  question.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const prompt = question.value.trim();
    if (!prompt) {
      feedback.textContent = 'Please enter a question first.';
      question.focus();
      return;
    }

    appendPortfolioChatMessage(transcript, 'visitor', prompt);
    question.value = '';
    question.disabled = true;
    submit.disabled = true;
    feedback.textContent = 'Thinking...';

    try {
      const requestPayload = { question: prompt };
      if (conversationSessionId) {
        requestPayload.conversation_session_id = conversationSessionId;
      }
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload)
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || typeof payload.answer !== 'string') {
        throw new Error(typeof payload.error === 'string' ? payload.error : 'The assistant could not answer right now.');
      }

      appendPortfolioChatMessage(
        transcript,
        'assistant',
        payload.answer,
        payload.citations,
        payload.diagram,
        payload.sections,
        payload.diagrams
      );
      feedback.textContent = payload.grounded
        ? 'Answer grounded in approved public sources.'
        : payload.mode === 'conversation'
          ? 'General conversation reply. Portfolio facts are cited when used.'
          : 'No sufficiently relevant approved source was found.';
    } catch (error) {
      appendPortfolioChatMessage(
        transcript,
        'assistant',
        error instanceof Error ? error.message : 'The assistant could not answer right now.'
      );
      feedback.textContent = 'No answer was generated from unverified information.';
    } finally {
      question.disabled = false;
      submit.disabled = false;
      question.focus();
    }
  });
}

function setAboutChatLayerOpen(toggle, panel, shouldOpen) {
  if (shouldOpen) {
    const motionVersion = cancelAboutChatMotion();
    delete panel.dataset.aboutChatClosing;
    panel.hidden = false;
    toggle.setAttribute('aria-expanded', 'true');
    setAboutChatWindowMaximized(panel, panel.classList.contains('is-maximized'));
    window.requestAnimationFrame(() => {
      if (motionVersion !== aboutChatMotionVersion || panel.hidden) return;
      const animation = playAboutChatAnimation(
        panel,
        [
          { opacity: 0, transform: 'translate3d(0, 0.8rem, 0) scale(0.985)' },
          { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' }
        ],
        'panel'
      );
      void waitForAboutChatAnimation(animation).then(() => {
        if (motionVersion === aboutChatMotionVersion) {
          clearAboutChatAnimation(animation, 'panel');
        }
      });
      panel.querySelector('#aboutChatQuestion')?.focus({ preventScroll: true });
    });
    return;
  }

  if (panel.hidden || panel.dataset.aboutChatClosing === 'true') return;

  restoreAboutChatVisualFocus(panel, false);
  const motionVersion = cancelAboutChatMotion();
  const wasMaximized = panel.classList.contains('is-maximized');
  const backdrop = ensureAboutChatBackdrop();
  panel.dataset.aboutChatClosing = 'true';
  toggle.setAttribute('aria-expanded', 'false');
  const panelAnimation = playAboutChatAnimation(
    panel,
    [
      { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' },
      { opacity: 0, transform: 'translate3d(0, 0.8rem, 0) scale(0.985)' }
    ],
    'panel'
  );
  const backdropAnimation = wasMaximized && !backdrop.hidden
    ? playAboutChatAnimation(backdrop, [{ opacity: 1 }, { opacity: 0 }], 'backdrop')
    : null;

  void Promise.all([
    waitForAboutChatAnimation(panelAnimation),
    waitForAboutChatAnimation(backdropAnimation)
  ]).then(() => {
    if (motionVersion !== aboutChatMotionVersion) return;

    panel.hidden = true;
    updateAboutChatWindowMaximizedState(panel, false);
    backdrop.hidden = true;
    document.body.classList.remove('about-chat-window-maximized');
    clearAboutChatAnimation(panelAnimation, 'panel');
    clearAboutChatAnimation(backdropAnimation, 'backdrop');
    delete panel.dataset.aboutChatClosing;
    toggle.focus({ preventScroll: true });
  });
}

function ensureAboutDesk() {
  const aboutSection = document.querySelector('.about-section');
  const aboutContainer = aboutSection?.querySelector('.about-container');
  const highlights = aboutContainer?.querySelector('.lux-list');
  const skillsBox = aboutContainer?.querySelector('.skills-box');

  if (!aboutSection || !aboutContainer || !highlights || !skillsBox) return;

  let aboutCopy = aboutContainer.querySelector('.about-copy');
  if (!aboutCopy) {
    aboutCopy = document.createElement('div');
    aboutCopy.className = 'about-copy';
    aboutContainer.insertBefore(aboutCopy, highlights);
    aboutCopy.append(highlights);
  }

  let highlightsHeading = aboutCopy.querySelector('.about-highlights-heading');
  if (!highlightsHeading) {
    highlightsHeading = document.createElement('h4');
    highlightsHeading.className = 'about-highlights-heading';
    aboutCopy.insertBefore(highlightsHeading, highlights);
  }
  highlightsHeading.textContent = 'Highlights';

  const backgroundRow = aboutSection.querySelector('.about-background-row');
  if (backgroundRow && backgroundRow.parentElement !== aboutCopy) {
    aboutCopy.append(backgroundRow);
  }

  let sideRail = aboutContainer.querySelector('.about-side-rail');
  if (!sideRail) {
    sideRail = document.createElement('aside');
    sideRail.className = 'about-side-rail';
    sideRail.setAttribute('aria-label', 'Skills and portfolio assistant');
    aboutContainer.append(sideRail);
  }

  if (skillsBox.parentElement !== sideRail) {
    sideRail.prepend(skillsBox);
  }

  let toggle = sideRail.querySelector('.about-chat-toggle');
  if (!toggle) {
    toggle = document.createElement('button');
    toggle.className = 'about-chat-toggle';
    toggle.id = 'aboutChatToggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', 'aboutChatPanel');
    sideRail.append(toggle);
  }

  let toggleMark = toggle.querySelector('.about-chat-toggle-mark');
  if (!toggleMark) {
    toggleMark = document.createElement('span');
    toggleMark.className = 'about-chat-toggle-mark';
    toggleMark.setAttribute('aria-hidden', 'true');
    toggleMark.textContent = '+';
  }

  toggle.replaceChildren('Ask About Me (RAG) ', toggleMark);

  let panel = document.getElementById('aboutChatPanel') || sideRail.querySelector('.about-chat-panel');
  if (!panel) {
    panel = document.createElement('section');
    panel.className = 'about-chat-panel';
    panel.id = 'aboutChatPanel';
    panel.hidden = true;
    panel.setAttribute('aria-labelledby', 'aboutChatStatus');
  }

  // The rail is animated with a transform, which would trap a fixed child.
  // Portal the live assistant to the document layer so it stays over the page
  // rather than increasing the About section's grid height.
  if (panel.parentElement !== document.body) {
    document.body.append(panel);
  }

  bindPortfolioAssistant(panel);
  const { close, maximize } = ensureAboutChatWindowControls(panel);

  if (toggle.dataset.aboutChatBound !== 'true') {
    toggle.dataset.aboutChatBound = 'true';
    toggle.addEventListener('click', () => {
      setAboutChatLayerOpen(toggle, panel, panel.hidden || panel.dataset.aboutChatClosing === 'true');
    });
  }

  if (panel.dataset.aboutChatLayerBound === 'true') return;

  panel.dataset.aboutChatLayerBound = 'true';
  close?.addEventListener('click', () => {
    setAboutChatLayerOpen(toggle, panel, false);
  });
  maximize?.addEventListener('click', () => {
    transitionAboutChatWindowMaximized(panel, !panel.classList.contains('is-maximized'));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      setAboutChatLayerOpen(toggle, panel, false);
    }
  });
}

ensureAboutDesk();

function setupAboutReveal() {
  const aboutSection = document.querySelector('.about-section');

  if (!aboutSection) return;

  const revealAbout = () => {
    aboutSection.classList.add('about-is-visible');
  };

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    revealAbout();
    return;
  }

  aboutSection.querySelectorAll('.lux-list li').forEach((item, index) => {
    item.style.setProperty('--about-reveal-delay', `${140 + (index * 105)}ms`);
  });
  aboutSection.classList.add('about-reveal-ready');

  if (!('IntersectionObserver' in window)) {
    window.requestAnimationFrame(revealAbout);
    return;
  }

  const aboutObserver = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;

    revealAbout();
    aboutObserver.disconnect();
  }, { threshold: 0.16 });

  aboutObserver.observe(aboutSection);
}

setupAboutReveal();

const heroStage = document.querySelector('.home-bg');
const heroPortrait = document.querySelector('.hero-portrait-reveal');

function ensureHeroPortraitSource() {
  const portraitImage = heroPortrait?.querySelector('img');

  if (!portraitImage) return;

  portraitImage.src = '/static/images/profile-portrait-decontaminated.png';
}

ensureHeroPortraitSource();

const heroDesktopQuery = window.matchMedia('(min-width: 761px)');
const heroRevealDistance = 960;
const heroRevealStopProgress = 0.7;
const heroRevealEase = 0.16;
const heroRevealSnapThreshold = 0.001;
let heroRevealProgress = 0;
let heroRevealTarget = 0;
let heroRevealFrame = null;

function heroPortraitIsFullyRevealed() {
  return heroRevealTarget === heroRevealStopProgress
    && heroRevealProgress === heroRevealStopProgress;
}

function shouldLockHeroScroll() {
  return heroDesktopQuery.matches
    && !heroPortraitIsFullyRevealed()
    && !document.body.classList.contains('recruiter-mode-active');
}

function renderHeroPortrait() {
  const shouldLockHero = shouldLockHeroScroll();

  document.documentElement.classList.toggle('hero-reveal-locked', shouldLockHero);
  document.body.classList.toggle('hero-reveal-locked', shouldLockHero);

  if (!heroStage || !heroPortrait) return;

  const offset = (1 - heroRevealProgress) * 112;
  const opacity = Math.min(1, heroRevealProgress * 1.6);

  heroStage.style.setProperty('--hero-portrait-offset', `${offset}%`);
  heroStage.style.setProperty('--hero-portrait-opacity', String(opacity));
  heroStage.dataset.portraitRevealed = String(heroPortraitIsFullyRevealed());
}

function animateHeroPortrait() {
  const difference = heroRevealTarget - heroRevealProgress;

  if (Math.abs(difference) < heroRevealSnapThreshold) {
    heroRevealProgress = heroRevealTarget;
    heroRevealFrame = null;
    renderHeroPortrait();
    return;
  }

  heroRevealProgress += difference * heroRevealEase;
  renderHeroPortrait();
  heroRevealFrame = window.requestAnimationFrame(animateHeroPortrait);
}

function startHeroPortraitAnimation() {
  if (heroRevealFrame !== null) return;

  heroRevealFrame = window.requestAnimationFrame(animateHeroPortrait);
}

function setHeroPortraitProgress(progress) {
  const boundedProgress = Math.min(heroRevealStopProgress, Math.max(0, progress));

  heroRevealTarget = boundedProgress;
  heroRevealProgress = boundedProgress;

  if (heroRevealFrame !== null) {
    window.cancelAnimationFrame(heroRevealFrame);
    heroRevealFrame = null;
  }

  renderHeroPortrait();
}

function canControlHeroPortrait(delta) {
  if (!heroStage || !heroPortrait || !heroDesktopQuery.matches) return false;
  if (document.body.classList.contains('recruiter-mode-active')) return false;

  if (delta > 0) {
    return heroRevealTarget < heroRevealStopProgress
      || heroRevealProgress < heroRevealStopProgress;
  }

  return delta < 0
    && (heroRevealTarget > 0 || heroRevealProgress > 0)
    && window.scrollY <= 1;
}

function advanceHeroPortrait(delta) {
  const nextProgress = Math.min(
    heroRevealStopProgress,
    Math.max(0, heroRevealTarget + delta / heroRevealDistance)
  );

  if (nextProgress === heroRevealTarget) {
    startHeroPortraitAnimation();
    return;
  }

  heroRevealTarget = nextProgress;
  renderHeroPortrait();
  startHeroPortraitAnimation();
}

function normaliseWheelDelta(event) {
  if (event.deltaMode === 1) return event.deltaY * 16;
  if (event.deltaMode === 2) return event.deltaY * window.innerHeight;
  return event.deltaY;
}

window.addEventListener('wheel', event => {
  if (event.ctrlKey) return;

  const delta = normaliseWheelDelta(event);
  if (!canControlHeroPortrait(delta)) return;

  event.preventDefault();
  advanceHeroPortrait(delta);
}, { passive: false });

window.addEventListener('scroll', () => {
  if (!shouldLockHeroScroll() || window.scrollY <= 1) return;

  window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
}, { passive: true });

window.addEventListener('keydown', event => {
  if (event.altKey || event.ctrlKey || event.metaKey) return;

  const activeElement = document.activeElement;
  if (activeElement && activeElement.matches('a, button, input, select, textarea, [contenteditable="true"]')) return;

  const keyScrollDeltas = {
    ArrowDown: 120,
    ArrowUp: -120,
    PageDown: window.innerHeight * 0.8,
    PageUp: -window.innerHeight * 0.8,
    ' ': 160
  };
  const delta = keyScrollDeltas[event.key];

  if (!delta || !canControlHeroPortrait(delta)) return;

  event.preventDefault();
  advanceHeroPortrait(delta);
}, { capture: true });

heroDesktopQuery.addEventListener('change', () => {
  if (heroDesktopQuery.matches) return;

  setHeroPortraitProgress(0);
});

document.querySelectorAll('.nav-links-header a[href^="#"]').forEach(link => {
  link.addEventListener('click', () => {
    if (link.getAttribute('href') === '#top') return;

    setHeroPortraitProgress(1);
  });
});

renderHeroPortrait();


// Keep the skills ticker off the main thread whenever it is outside the viewport.
function initialiseSkillsTicker() {
  const skillsList = document.getElementById("skills-list");
  if (!skillsList) return;

  const items = Array.from(skillsList.children);
  if (!items.length) return;

  items.forEach(item => {
    const clone = item.cloneNode(true);
    skillsList.appendChild(clone);
  });

  let position = 0;
  let itemHeight = items[0].offsetHeight || 32;
  let frameId = 0;
  let previousTimestamp = 0;
  let isVisible = false;
  const skillsViewport = skillsList.parentElement || skillsList;

  function stopTicker() {
    if (frameId) {
      cancelAnimationFrame(frameId);
    }

    frameId = 0;
    previousTimestamp = 0;
    skillsList.style.willChange = 'auto';
  }

  function tick(timestamp) {
    if (!isVisible || document.hidden) {
      frameId = 0;
      previousTimestamp = 0;
      return;
    }

    const elapsed = previousTimestamp ? Math.min(timestamp - previousTimestamp, 40) : 16.67;
    previousTimestamp = timestamp;
    position += elapsed * 0.03;

    if (position >= itemHeight * items.length) {
      position = 0;
    }

    skillsList.style.transform = `translate3d(0, -${position.toFixed(2)}px, 0)`;
    frameId = requestAnimationFrame(tick);
  }

  function startTicker() {
    if (frameId || !isVisible || document.hidden) return;
    skillsList.style.willChange = 'transform';
    frameId = requestAnimationFrame(tick);
  }

  if ('IntersectionObserver' in window) {
    const visibilityObserver = new IntersectionObserver(entries => {
      isVisible = entries.some(entry => entry.isIntersecting);
      if (isVisible) startTicker();
      else stopTicker();
    }, { threshold: 0.05 });

    visibilityObserver.observe(skillsViewport);
  } else {
    isVisible = true;
    startTicker();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopTicker();
    else startTicker();
  });
  window.addEventListener('resize', () => {
    itemHeight = items[0].offsetHeight || 32;
  }, { passive: true });
}

if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', initialiseSkillsTicker, { once: true });
} else {
  initialiseSkillsTicker();
}

document.querySelectorAll('.mobile-nav-dropdown a').forEach(link => {
  link.addEventListener('click', function () {
    document.body.classList.remove('nav-open');
  });
});

const grid = document.getElementById('projectsGrid');
const carouselContainer = document.getElementById('projectsCarousel');
const carouselCardsContainer = document.getElementById('carouselCardsContainer');
const arrowLeft = document.getElementById('carouselArrowLeft');
const arrowRight = document.getElementById('carouselArrowRight');
const toggleBtn = document.getElementById('carouselToggleBtn');
const projectsHeadingNote = document.getElementById('projectsHeadingNote');
const projectsLiveDemoNote = document.getElementById('projectsLiveDemoNote');
const workSection = document.getElementById('work');
const carouselRow = carouselContainer ? carouselContainer.closest('.work-flex-row') : null;

if (projectsHeadingNote) {
  projectsHeadingNote.textContent = 'You can unroll and visit the projects to access the links and know more about them.';
}

if (carouselRow) {
  carouselRow.classList.add('project-carousel-row');
}

grid.querySelectorAll('.project-impact').forEach(impact => impact.remove());

function resolveCssLength(value, fallback) {
  const probe = document.createElement('div');
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  probe.style.pointerEvents = 'none';
  probe.style.width = value;
  document.body.appendChild(probe);
  const resolved = parseFloat(getComputedStyle(probe).width);
  probe.remove();
  return Number.isFinite(resolved) ? resolved : fallback;
}

let carouselVarsCache = null;

function refreshCarouselVars() {
  const styles = getComputedStyle(document.documentElement);
  carouselVarsCache = {
    radius: resolveCssLength(styles.getPropertyValue('--carousel-radius'), 600),
    cardW: resolveCssLength(styles.getPropertyValue('--carousel-card-width'), 240),
    cardH: resolveCssLength(styles.getPropertyValue('--carousel-card-height'), 320),
    scaleFactor: parseFloat(styles.getPropertyValue('--carousel-scale-factor')) || 0.5
  };
  return carouselVarsCache;
}

function getCarouselVars() {
  return carouselVarsCache || refreshCarouselVars();
}
const aboutWorkPanel = document.getElementById('aboutWorkPanel');

function normalizeProjectText(element) {
  const copy = element.cloneNode(true);
  copy.querySelectorAll('br').forEach(lineBreak => lineBreak.replaceWith(' '));
  return copy.textContent.replace(/\s+/g, ' ').trim();
}

const projectActionConfig = [
  { detailPath: '/projects/5g-handover-stability-aware-ml', liveUrl: '/mobility' },
  { detailPath: '/projects/cardio-risk-predictor' },
  { detailPath: '/projects/digital-twin-fleet-smart-vehicle' },
  { detailPath: '/projects/parkinsons-disease-detection' },
  {
    detailPath: '/projects/closed-loop-automation',
    title: 'Closed Loop Automation',
    awardLabel: '3rd Prize Winner'
  },
  { detailPath: '/projects/fraud-transaction-detector' },
  { detailPath: '/projects/automl-system' }
];

const projectCards = Array.from(grid.querySelectorAll('.card.landscape-card')).map((card, index) => {
  const titleElement = card.querySelector('h4');
  const descriptionElement = card.querySelector('p');
  const githubLink = card.querySelector('.project-github-link');
  const actions = projectActionConfig[index] || {};
  const themeClass = Array.from(card.classList)
    .filter(className => className.startsWith('project-') && className.endsWith('-card'))
    .join(' ');

  return {
    title: actions.title || titleElement.innerHTML,
    titleText: actions.title || normalizeProjectText(titleElement),
    desc: descriptionElement.innerHTML,
    descText: normalizeProjectText(descriptionElement),
    imgSrc: card.querySelector('.card-img img').src,
    imgAlt: card.querySelector('.card-img img').alt,
    detailPath: card.dataset.detailPath || actions.detailPath || '#projects',
    liveUrl: card.dataset.liveUrl || actions.liveUrl || '',
    awardLabel: actions.awardLabel || '',
    githubUrl: githubLink?.dataset.githubUrl || '',
    themeClass
  };
});

document.querySelector('.recruiter-project[href="/#work"] h2')?.replaceChildren('Closed Loop Automation');

let carouselCardElements = [];
let carouselCardSizeKey = '';

function buildCarouselCards() {
  const fragment = document.createDocumentFragment();

  carouselCardElements = projectCards.map((project, index) => {
    const card = document.createElement('article');
    card.className = ['carousel-card', project.themeClass].filter(Boolean).join(' ');
    card.dataset.projectIndex = String(index);
    card.setAttribute('aria-label', project.titleText);

    card.innerHTML = `
      <div class="card-img">
        <img src="${project.imgSrc}" alt="${project.imgAlt}" decoding="async">
      </div>
      <div class="card-content">
        <h4>${project.title}</h4>
        <p>${project.desc}</p>
      </div>
    `;

    fragment.appendChild(card);
    return card;
  });

  carouselCardsContainer.replaceChildren(fragment);
  carouselCardSizeKey = '';
}

function applyCarouselCardDimensions(cardW, cardH) {
  const sizeKey = `${cardW}:${cardH}`;
  if (sizeKey === carouselCardSizeKey) return;

  carouselCardElements.forEach(card => {
    card.style.width = `${cardW}px`;
    card.style.height = `${cardH}px`;
  });

  carouselCardSizeKey = sizeKey;
}

function ensureProjectArchive() {
  let archive = document.getElementById('projectArchive');

  if (!archive) {
    archive = document.createElement('div');
    archive.id = 'projectArchive';
    archive.className = 'project-archive';
    archive.setAttribute('aria-label', 'Project archive');
    const archiveAnchor = grid.closest('.work-flex-row') || grid;
    archiveAnchor.insertAdjacentElement('afterend', archive);
  }

  let index = archive.querySelector('#projectArchiveIndex');
  let preview = archive.querySelector('#projectArchivePreview');

  if (!index || !preview) {
    archive.innerHTML = `
      <ol class="project-archive-index" id="projectArchiveIndex" aria-label="Projects"></ol>
      <article class="project-archive-preview" id="projectArchivePreview" aria-live="polite"></article>
    `;
    index = archive.querySelector('#projectArchiveIndex');
    preview = archive.querySelector('#projectArchivePreview');
  }

  archive.hidden = true;
  return { archive, index, preview };
}

const {
  archive: projectArchive,
  index: projectArchiveIndex,
  preview: projectArchivePreview
} = ensureProjectArchive();

function scrollToAboutAssistant(openDelay = 1000) {
  const aboutAssistant = document.getElementById('aboutChatToggle');
  const aboutSection = document.getElementById('about');

  // Deliberate section navigation should not be held by the hero scroll reveal.
  setHeroPortraitProgress(heroRevealStopProgress);

  if (aboutAssistant) {
    const navbarClearance = 96;
    const targetTop = window.scrollY + aboutAssistant.getBoundingClientRect().top - navbarClearance;

    window.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
    window.setTimeout(() => {
      if (aboutAssistant.getAttribute('aria-expanded') !== 'true') {
        aboutAssistant.click();
      }
    }, openDelay);
    return;
  }

  aboutSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function ensureRagProjectFeature() {
  let feature = document.getElementById('ragProjectFeature');

  if (!feature) {
    feature = document.createElement('article');
    feature.id = 'ragProjectFeature';
    feature.className = 'project-rag-feature';
    feature.setAttribute('aria-labelledby', 'ragProjectTitle');
    projectArchive.insertAdjacentElement('afterend', feature);
  }

  let trigger = feature.querySelector('[data-open-about-assistant]');
  if (!trigger) {
    feature.innerHTML = `
      <button class="project-rag-trigger" type="button" data-open-about-assistant aria-controls="aboutChatPanel">
        <span class="project-rag-status">Source-Grounded</span>
        <span class="project-rag-content">
          <span class="project-rag-title" id="ragProjectTitle">Source-Cited RAG Assistant</span>
          <span class="project-rag-copy">An evidence-first portfolio assistant with approved-source retrieval, validated citations, safe multi-turn context, and approved architecture diagrams.</span>
        </span>
        <span class="project-rag-cta">Open Ask About Me <span aria-hidden="true">&#8599;</span></span>
      </button>
    `;
    trigger = feature.querySelector('[data-open-about-assistant]');
  }

  if (trigger.dataset.ragBound === 'true') return;

  trigger.dataset.ragBound = 'true';
  trigger.addEventListener('click', () => {
    scrollToAboutAssistant();
  });
}

ensureRagProjectFeature();

function ensureHeroActions() {
  const hero = document.querySelector('.home-bg');
  if (!hero) return;

  let actions = hero.querySelector('.hero-actions');
  if (!actions) {
    actions = document.createElement('div');
    actions.className = 'hero-actions';
    actions.setAttribute('aria-label', 'Portfolio actions');
    actions.innerHTML = `
      <button class="hero-action hero-action-primary" type="button" data-hero-about-assistant>
        Ask About Me (RAG) <span aria-hidden="true">&#8599;</span>
      </button>
      <a class="hero-action" href="/static/My%20Resume.pdf" target="_blank" rel="noopener">
        View Resume <span aria-hidden="true">&#8599;</span>
      </a>
    `;
    hero.append(actions);
  }

  const aboutAction = actions.querySelector('[data-hero-about-assistant]');
  if (!aboutAction || aboutAction.dataset.heroActionBound === 'true') return;

  aboutAction.dataset.heroActionBound = 'true';
  aboutAction.addEventListener('click', () => scrollToAboutAssistant());
}

ensureHeroActions();

let activeArchiveProjectIndex = 0;
let projectUnrollFrame = 0;
let projectUnrollTimeout = 0;
let isProjectUnrolling = false;
let isProjectRerolling = false;
let carouselAngleBeforeUnroll = 0;
let carouselActiveIndexBeforeUnroll = 0;
const projectBridgeDuration = 980;
const projectBridgeResolveDuration = 360;
const projectBridgeEasing = 'cubic-bezier(0.4, 0, 0.2, 1)';
let projectTransitionGhosts = [];

function projectNumber(index) {
  return String(index + 1).padStart(2, '0');
}

function selectArchiveProject(index, animate = true) {
  if (!projectCards.length) return;

  activeArchiveProjectIndex = Math.max(0, Math.min(index, projectCards.length - 1));
  const project = projectCards[activeArchiveProjectIndex];
  const liveProjectLink = project.liveUrl
    ? `<a class="project-archive-link project-archive-live-link" href="${project.liveUrl}">View Project <span aria-hidden="true">&#8599;</span></a>`
    : '';
  const githubLink = project.githubUrl
    ? `<a class="project-archive-github" href="${project.githubUrl}" target="_blank" rel="noopener" aria-label="Open ${project.titleText} on GitHub"><img src="/static/images/github.png" alt=""></a>`
    : '';
  const awardBadge = project.awardLabel
    ? `<span class="project-archive-award">${project.awardLabel}</span>`
    : '';

  projectArchivePreview.classList.remove('is-updating');
  projectArchivePreview.innerHTML = `
    <div class="project-archive-media">
      <img src="${project.imgSrc}" alt="${project.imgAlt}">
    </div>
    <div class="project-archive-copy">
      <p class="project-archive-kicker">Project ${projectNumber(activeArchiveProjectIndex)}</p>
      <h4>${project.title}</h4>
      <p>${project.descText}</p>
      <div class="project-archive-actions">
        <a class="project-archive-link" href="${project.detailPath}">Know More <span aria-hidden="true">&#8599;</span></a>
        ${liveProjectLink}
        ${githubLink}
      </div>
    </div>
    ${awardBadge}
  `;

  projectArchiveIndex.querySelectorAll('.project-archive-index-button').forEach((button, buttonIndex) => {
    const selected = buttonIndex === activeArchiveProjectIndex;
    button.classList.toggle('is-selected', selected);
    button.setAttribute('aria-current', selected ? 'true' : 'false');
  });

  if (animate && !projectArchive.hidden) {
    requestAnimationFrame(() => projectArchivePreview.classList.add('is-updating'));
  }
}

function renderProjectArchive() {
  projectArchiveIndex.innerHTML = projectCards.map((project, index) => `
    <li class="project-archive-index-item" style="--archive-item-index: ${index}">
      <button class="project-archive-index-button" type="button" data-project-index="${index}" aria-controls="projectArchivePreview">
        <span class="project-archive-number">${projectNumber(index)}</span>
        <span class="project-archive-title">${project.titleText}</span>
      </button>
    </li>
  `).join('');

  projectArchiveIndex.querySelectorAll('.project-archive-index-button').forEach(button => {
    const index = Number(button.dataset.projectIndex);
    const activate = () => selectArchiveProject(index);
    button.addEventListener('pointerenter', activate);
    button.addEventListener('focus', activate);
    button.addEventListener('click', activate);
  });

  selectArchiveProject(activeArchiveProjectIndex, false);
}

function captureCarouselCardRecords() {
  return Array.from(carouselCardsContainer.querySelectorAll('.carousel-card')).map(card => ({
    card,
    index: Number(card.dataset.projectIndex),
    rect: card.getBoundingClientRect(),
    isActive: card.classList.contains('active'),
    isSide: card.classList.contains('side')
  })).filter(record => record.rect.width > 0 && record.rect.height > 0);
}

function getActiveCarouselProjectIndex() {
  const activeCard = carouselCardsContainer.querySelector('.carousel-card.active');
  const index = activeCard ? Number(activeCard.dataset.projectIndex) : NaN;
  return Number.isFinite(index) ? index : carouselActiveIndexBeforeUnroll;
}

function getCarouselAngleForProject(index) {
  const cardStep = 360 / projectCards.length;
  return carouselAngleBeforeUnroll - (index - carouselActiveIndexBeforeUnroll) * cardStep;
}

function clearProjectTransitionGhosts() {
  projectTransitionGhosts.forEach(ghost => ghost.remove());
  projectTransitionGhosts = [];
}

function createProjectTransitionGhost(sourceElement, sourceRect, modifier) {
  if (!sourceElement || !sourceRect.width || !sourceRect.height) return null;

  const ghost = sourceElement.cloneNode(true);
  const sourceOpacity = Number.parseFloat(getComputedStyle(sourceElement).opacity);

  ghost.classList.add('project-transition-ghost', modifier);
  ghost.style.position = 'fixed';
  ghost.style.top = `${sourceRect.top}px`;
  ghost.style.left = `${sourceRect.left}px`;
  ghost.style.width = `${sourceRect.width}px`;
  ghost.style.height = `${sourceRect.height}px`;
  ghost.style.margin = '0';
  ghost.style.opacity = String(Number.isFinite(sourceOpacity) ? sourceOpacity : 1);
  ghost.style.transformOrigin = 'top left';
  ghost.style.transform = 'translate3d(0, 0, 0) scale(1, 1)';
  ghost.style.filter = 'none';
  ghost.style.zIndex = '950';
  ghost.style.pointerEvents = 'none';
  ghost.style.transition = 'none';
  document.body.appendChild(ghost);
  void ghost.offsetWidth;

  projectTransitionGhosts.push(ghost);
  return ghost;
}

function settleProjectTransitionGhost(ghost, targetRect, targetOpacity) {
  if (!ghost || !targetRect || !targetRect.width || !targetRect.height) return;

  const sourceRect = ghost.getBoundingClientRect();
  const translateX = targetRect.left - sourceRect.left;
  const translateY = targetRect.top - sourceRect.top;
  const scaleX = targetRect.width / sourceRect.width;
  const scaleY = targetRect.height / sourceRect.height;

  ghost.style.transition = `transform ${projectBridgeDuration}ms ${projectBridgeEasing}, opacity ${projectBridgeDuration}ms ease, padding ${projectBridgeDuration}ms ${projectBridgeEasing}, border-radius ${projectBridgeDuration}ms ${projectBridgeEasing}`;

  requestAnimationFrame(() => {
    ghost.classList.add('is-settling');
    ghost.style.transform = `translate3d(${translateX.toFixed(2)}px, ${translateY.toFixed(2)}px, 0) scale(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)})`;
    ghost.style.opacity = String(targetOpacity);
  });
}

document.querySelectorAll('.project-github-link').forEach(link => {
  function openRepository(event) {
    event.preventDefault();
    event.stopPropagation();
    const url = link.dataset.githubUrl;
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
  }

  link.addEventListener('click', openRepository);
  link.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
      openRepository(event);
    }
  });
});

document.querySelectorAll('.project-linkedin-award').forEach(link => {
  function openBadgeLink(event) {
    event.preventDefault();
    event.stopPropagation();
    const url = link.dataset.linkedinUrl || link.dataset.documentUrl;
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
  }

  link.addEventListener('click', openBadgeLink);
  link.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
      openBadgeLink(event);
    }
  });
});

let angle = 0;
let animating = false;
let carouselAnimationFrame = 0;
let carouselResizeFrame = 0;
const N = projectCards.length;
const step = 360 / N;
let dragging = false;
let dragStartX = 0;

function cancelCarouselMotion() {
  if (carouselAnimationFrame) {
    cancelAnimationFrame(carouselAnimationFrame);
    carouselAnimationFrame = 0;
  }

  animating = false;
  workSection.classList.remove('is-carousel-moving');
}

function animateTo(targetAngle) {
  if (animating) return;

  cancelCarouselMotion();
  animating = true;
  workSection.classList.add('is-carousel-moving');
  const startAngle = angle;
  const duration = 700;
  const startTime = performance.now();

  function animate(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    angle = startAngle + (targetAngle - startAngle) * progress;
    renderCarousel();
    if (progress < 1) {
      carouselAnimationFrame = requestAnimationFrame(animate);
    } else {
      angle = targetAngle;
      renderCarousel();
      animating = false;
      carouselAnimationFrame = 0;
      workSection.classList.remove('is-carousel-moving');
    }
  }

  carouselAnimationFrame = requestAnimationFrame(animate);
}

function renderCarousel() {
  const N = projectCards.length;

  if (carouselCardElements.length !== N) {
    buildCarouselCards();
  }

  const { radius, cardW, cardH, scaleFactor } = getCarouselVars();
  applyCarouselCardDimensions(cardW, cardH);

  for (let i = 0; i < N; i++) {
    const card = carouselCardElements[i];

    const theta = (360 / N) * i + angle;
    const thetaRad = (theta * Math.PI) / 180;

    // X/Z placement
    const x = Math.sin(thetaRad) * radius;
    const z = Math.cos(thetaRad) * radius;

    const rel = ((theta % 360) + 360) % 360;
    const distance = Math.min(
      Math.abs(rel - 0),
      Math.abs(rel - 360)
    );

    // Scale using CSS var
    const scale = 1 - scaleFactor * Math.min(distance / 180, 1);

    card.style.transform = `translateX(-50%) translate3d(${x.toFixed(2)}px, -50%, ${z.toFixed(2)}px) rotateY(${theta.toFixed(2)}deg) scale(${scale.toFixed(2)})`;

    // Opacity fade
    const opacity = Math.cos((distance / 180) * (Math.PI / 2));
    card.style.opacity = opacity.toFixed(2);

    // Layering
    card.style.zIndex = String(Math.round(100 - distance));

    card.classList.toggle('active', distance < 20);
    card.classList.toggle('side', distance >= 20 && distance < 80);
    card.classList.toggle('far', distance >= 80 && distance < 160);
    card.classList.toggle('hidden', distance >= 160);
  }
}

function handleCarouselViewportChange() {
  if (carouselResizeFrame) return;

  carouselResizeFrame = requestAnimationFrame(() => {
    carouselResizeFrame = 0;
    carouselVarsCache = null;
    renderCarousel();
  });
}

window.addEventListener('resize', handleCarouselViewportChange, { passive: true });
window.addEventListener('orientationchange', handleCarouselViewportChange, { passive: true });
renderCarousel();
showCarousel();

function showCarousel() {
  cancelCarouselMotion();

  if (projectUnrollFrame) {
    cancelAnimationFrame(projectUnrollFrame);
    projectUnrollFrame = 0;
  }

  if (projectUnrollTimeout) {
    window.clearTimeout(projectUnrollTimeout);
    projectUnrollTimeout = 0;
  }

  clearProjectTransitionGhosts();
  projectArchive.classList.remove('is-bridge-preparing');
  isProjectUnrolling = false;
  isProjectRerolling = false;
  grid.style.display = 'none';
  projectArchive.hidden = true;
  projectsHeadingNote.style.display = 'block';
  projectsLiveDemoNote.style.display = 'none';
  carouselContainer.classList.add('active');
  toggleBtn.hidden = false;
  toggleBtn.disabled = false;
  toggleBtn.textContent = 'Unroll';
  toggleBtn.setAttribute('aria-expanded', 'false');
  workSection.classList.remove('is-unrolling', 'is-unrolled', 'is-rerolling', 'is-restoring', 'is-carousel-moving');

  if (carouselRow) {
    carouselRow.hidden = false;
    carouselRow.removeAttribute('aria-hidden');
    carouselRow.style.height = '';
  }

  aboutWorkPanel.hidden = false;
  aboutWorkPanel.classList.remove('expanded');
  aboutWorkPanel.classList.add('minimized');
  renderProjectArchive();
  renderCarousel();
}

function showProjectArchive() {
  cancelCarouselMotion();

  if (projectUnrollFrame) {
    cancelAnimationFrame(projectUnrollFrame);
    projectUnrollFrame = 0;
  }

  if (projectUnrollTimeout) {
    window.clearTimeout(projectUnrollTimeout);
    projectUnrollTimeout = 0;
  }

  clearProjectTransitionGhosts();
  projectArchive.classList.remove('is-bridge-preparing');
  isProjectUnrolling = false;
  isProjectRerolling = false;
  carouselAngleBeforeUnroll = angle;
  renderProjectArchive();
  projectArchive.hidden = false;
  grid.style.display = 'none';
  projectsHeadingNote.style.display = 'none';
  projectsLiveDemoNote.style.display = 'none';
  carouselContainer.classList.remove('active');
  toggleBtn.hidden = false;
  toggleBtn.disabled = false;
  toggleBtn.textContent = 'Roll Again';
  toggleBtn.setAttribute('aria-expanded', 'true');
  aboutWorkPanel.hidden = true;
  workSection.classList.remove('is-unrolling', 'is-carousel-moving');
  workSection.classList.add('is-unrolled');

  if (carouselRow) {
    carouselRow.hidden = true;
    carouselRow.setAttribute('aria-hidden', 'true');
    carouselRow.style.height = '';
  }
}

function showGrid() {
  showProjectArchive();
}

function completeProjectUnroll() {
  const cardRecords = captureCarouselCardRecords();
  const activeRecord = cardRecords.find(record => record.isActive) || cardRecords[0];
  const activeIndex = activeRecord ? activeRecord.index : carouselActiveIndexBeforeUnroll;

  activeArchiveProjectIndex = activeIndex;
  renderProjectArchive();
  selectArchiveProject(activeIndex, false);
  projectArchive.hidden = false;
  projectArchive.classList.add('is-bridge-preparing');

  // Set the final archive geometry before the card copies begin travelling into it.
  projectsHeadingNote.style.display = 'none';
  projectsLiveDemoNote.style.display = 'none';
  aboutWorkPanel.hidden = true;
  carouselContainer.classList.remove('active');

  if (carouselRow) {
    carouselRow.hidden = true;
    carouselRow.setAttribute('aria-hidden', 'true');
    carouselRow.style.height = '';
  }

  workSection.classList.add('is-unrolled');

  const previewTarget = projectArchivePreview
    .querySelector('.project-archive-media')
    ?.getBoundingClientRect();
  const activeGhost = activeRecord
    ? createProjectTransitionGhost(
      activeRecord.card,
      activeRecord.rect,
      'project-transition-ghost--preview'
    )
    : null;

  settleProjectTransitionGhost(activeGhost, previewTarget, 0.52);

  cardRecords
    .filter(record => record.isSide)
    .slice(0, 2)
    .forEach(record => {
      const target = projectArchiveIndex
        .querySelector(`[data-project-index="${record.index}"]`)
        ?.getBoundingClientRect();
      const ghost = createProjectTransitionGhost(
        record.card,
        record.rect,
        'project-transition-ghost--index'
      );

      settleProjectTransitionGhost(ghost, target, 0.18);
    });

  projectUnrollTimeout = window.setTimeout(() => {
    projectArchive.classList.remove('is-bridge-preparing');
    projectTransitionGhosts.forEach(ghost => {
      ghost.style.transition = `opacity ${projectBridgeResolveDuration}ms ease`;
      ghost.style.opacity = '0';
    });

    projectUnrollTimeout = window.setTimeout(() => {
      clearProjectTransitionGhosts();
      toggleBtn.hidden = false;
      toggleBtn.disabled = false;
      toggleBtn.textContent = 'Roll Again';
      toggleBtn.setAttribute('aria-expanded', 'true');

      isProjectUnrolling = false;
      isProjectRerolling = false;
      workSection.classList.remove('is-unrolling', 'is-carousel-moving');
      projectUnrollTimeout = 0;
    }, projectBridgeResolveDuration);
  }, projectBridgeDuration);
}

function startProjectUnroll() {
  if (isProjectUnrolling || isProjectRerolling || workSection.classList.contains('is-unrolled')) return;

  cancelCarouselMotion();
  isProjectUnrolling = true;
  carouselAngleBeforeUnroll = angle;
  carouselActiveIndexBeforeUnroll = getActiveCarouselProjectIndex();
  clearProjectTransitionGhosts();
  projectArchive.classList.remove('is-bridge-preparing');
  toggleBtn.disabled = true;
  toggleBtn.setAttribute('aria-expanded', 'true');
  workSection.classList.add('is-unrolling', 'is-carousel-moving');

  const startAngle = angle;
  const duration = 2000;
  const rotations = 3;
  const startTime = performance.now();

  function spinCarousel(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;

    angle = startAngle - 360 * rotations * eased;
    renderCarousel();

    if (progress < 1) {
      projectUnrollFrame = requestAnimationFrame(spinCarousel);
      return;
    }

    angle = startAngle - 360 * rotations;
    projectUnrollFrame = 0;
    renderCarousel();
    completeProjectUnroll();
  }

  projectUnrollFrame = requestAnimationFrame(spinCarousel);
}

function completeProjectReroll() {
  angle = carouselAngleBeforeUnroll;
  renderCarousel();
  projectArchive.hidden = true;
  projectArchive.classList.remove('is-bridge-preparing');

  if (carouselRow) {
    carouselRow.style.height = '';
  }

  workSection.classList.add('is-restoring');
  projectsHeadingNote.style.display = 'block';
  projectsLiveDemoNote.style.display = 'none';
  aboutWorkPanel.hidden = false;
  carouselContainer.classList.add('active');
  toggleBtn.hidden = false;
  toggleBtn.disabled = false;
  toggleBtn.textContent = 'Unroll';
  toggleBtn.setAttribute('aria-expanded', 'false');

  requestAnimationFrame(() => {
    workSection.classList.remove('is-rerolling', 'is-restoring', 'is-carousel-moving');
  });

  isProjectRerolling = false;
}

function startProjectReroll() {
  if (!workSection.classList.contains('is-unrolled') || isProjectUnrolling || isProjectRerolling) return;

  const sourceMedia = projectArchivePreview.querySelector('.project-archive-media');
  const sourceRect = sourceMedia ? sourceMedia.getBoundingClientRect() : null;
  const previewGhost = sourceMedia && sourceRect
    ? createProjectTransitionGhost(sourceMedia, sourceRect, 'project-transition-ghost--reroll-media')
    : null;

  isProjectRerolling = true;
  toggleBtn.disabled = true;
  workSection.classList.add('is-rerolling', 'is-carousel-moving');

  // Restore the normal layout now, while its original content remains visually quiet.
  projectsHeadingNote.style.display = 'block';
  projectsLiveDemoNote.style.display = 'none';
  aboutWorkPanel.hidden = false;

  if (carouselRow) {
    carouselRow.hidden = false;
    carouselRow.removeAttribute('aria-hidden');
    carouselRow.style.height = '';
  }

  carouselContainer.classList.add('active');
  angle = getCarouselAngleForProject(activeArchiveProjectIndex);
  renderCarousel();

  const targetCard = carouselCardsContainer.querySelector('.carousel-card.active');
  const targetMedia = targetCard ? targetCard.querySelector('.card-img') : null;
  const targetRect = targetMedia
    ? targetMedia.getBoundingClientRect()
    : targetCard?.getBoundingClientRect();
  settleProjectTransitionGhost(previewGhost, targetRect, 0.68);

  // The return spin begins immediately; only the forward Unroll keeps its deliberate pause.
  projectArchive.hidden = true;
  workSection.classList.remove('is-unrolled');

  const startAngle = angle;
  const targetAngle = carouselAngleBeforeUnroll;
  const duration = 2000;
  const startTime = performance.now();

  function spinCarouselBack(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;

    angle = startAngle + (targetAngle - startAngle) * eased;
    renderCarousel();

    if (progress < 1) {
      projectUnrollFrame = requestAnimationFrame(spinCarouselBack);
      return;
    }

    projectUnrollFrame = 0;
    completeProjectReroll();
  }

  projectUnrollFrame = requestAnimationFrame(spinCarouselBack);

  projectUnrollTimeout = window.setTimeout(() => {
    projectTransitionGhosts.forEach(ghost => {
      ghost.style.transition = `opacity ${projectBridgeResolveDuration}ms ease`;
      ghost.style.opacity = '0';
    });

    projectUnrollTimeout = window.setTimeout(() => {
      clearProjectTransitionGhosts();
      projectUnrollTimeout = 0;
    }, projectBridgeResolveDuration);
  }, projectBridgeDuration);
}

toggleBtn.addEventListener('click', () => {
  if (workSection.classList.contains('is-unrolled')) {
    startProjectReroll();
    return;
  }

  startProjectUnroll();
});

// Dragging support
// carouselCardsContainer.addEventListener('mousedown', e => {
//   dragging = true;
//   dragStartX = e.clientX;
// });

// window.addEventListener('mouseup', () => {
//   dragging = false;
// });

// carouselCardsContainer.addEventListener('touchstart', e => {
//   dragging = true;
//   dragStartX = e.touches[0].clientX;
// });
// window.addEventListener('touchmove', e => {
//   if (!dragging) return;
//   const dx = e.touches[0].clientX - dragStartX;
//   angle += dx * -0.4;
//   dragStartX = e.touches[0].clientX;
//   renderCarousel();
// });
// window.addEventListener('touchend', () => {
//   dragging = false;
// });

// Arrows
arrowLeft.addEventListener('click', () => {
  if (isProjectUnrolling || isProjectRerolling || !carouselContainer.classList.contains('active')) return;
  const step = 360 / projectCards.length;
  animateTo(angle + step);
  renderCarousel();
});

arrowRight.addEventListener('click', () => {
  if (isProjectUnrolling || isProjectRerolling || !carouselContainer.classList.contains('active')) return;
  const step = 360 / projectCards.length;
  animateTo(angle - step);
  renderCarousel();
});

const recruiterModeToggle = document.getElementById('recruiterModeToggle');
const recruiterModePanel = document.getElementById('recruiterMode');
const recruiterToggleText = recruiterModeToggle ? recruiterModeToggle.querySelector('.recruiter-toggle-text') : null;
const recruiterExitControls = document.querySelectorAll('[data-recruiter-exit]');

function setRecruiterMode(active, targetSelector) {
  document.body.classList.toggle('recruiter-mode-active', active);
  document.body.classList.remove('nav-open');
  renderHeroPortrait();

  if (recruiterModePanel) {
    recruiterModePanel.hidden = !active;
  }

  if (recruiterModeToggle) {
    recruiterModeToggle.setAttribute('aria-pressed', String(active));
  }

  if (recruiterToggleText) {
    recruiterToggleText.textContent = active ? 'Full Portfolio' : 'Summarize';
  }

  if (active) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  if (targetSelector) {
    if (targetSelector === '#work') {
      showGrid();
    }

    const target = document.querySelector(targetSelector);
    if (target) {
      requestAnimationFrame(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }
  }
}

if (recruiterModeToggle) {
  recruiterModeToggle.addEventListener('click', () => {
    const isActive = document.body.classList.contains('recruiter-mode-active');
    setRecruiterMode(!isActive);
  });
}

recruiterExitControls.forEach(control => {
  control.addEventListener('click', () => {
    if (control.hasAttribute('data-recruiter-open-assistant')) {
      setRecruiterMode(false);
      window.setTimeout(() => scrollToAboutAssistant(), 120);
      return;
    }

    setRecruiterMode(false, control.dataset.recruiterTarget);
  });
});

function ensureContactSection() {
  const contactSection = document.getElementById('contact');
  if (!contactSection || contactSection.querySelector('.contact-shell')) return;

  contactSection.className = 'contact-section content-section';
  contactSection.setAttribute('aria-labelledby', 'contact-heading');
  contactSection.innerHTML = `
    <div class="contact-shell">
      <h3 id="contact-heading" class="contact-heading" data-shadow=".Contact">.Contact</h3>
      <div class="contact-rule" aria-hidden="true"></div>
      <div class="contact-stage">
        <div class="contact-primary-action">
          <p class="contact-eyebrow">Start a conversation</p>
          <p class="contact-question">Open to learning and new opportunities.</p>
          <button class="contact-email-action" type="button" data-contact-open>
            <span>Email Me</span>
            <span class="contact-email-arrow" aria-hidden="true">&#8599;</span>
          </button>
        </div>
        <nav class="contact-social-rail" aria-label="Professional profiles">
          <p>Find me online</p>
          <a href="https://www.linkedin.com/in/mihir-lakhani-149504327/" target="_blank" rel="noopener">
            <img src="/static/images/linkedin-contact.png" alt=""><span>LinkedIn</span>
          </a>
          <a href="https://github.com/Mihir-Lakhani" target="_blank" rel="noopener">
            <img src="/static/images/github.png" alt=""><span>GitHub</span>
          </a>
        </nav>
      </div>
      <div class="contact-footer"><span>work.mihir454@gmail.com</span><span>Udaipur, Rajasthan</span></div>
    </div>`;

  const legacyFooter = contactSection.nextElementSibling;
  if (legacyFooter?.tagName === 'FOOTER') {
    legacyFooter.remove();
  }

  if (!document.getElementById('contactDialog')) {
    document.body.insertAdjacentHTML('beforeend', `
      <dialog id="contactDialog" class="contact-dialog" aria-labelledby="contact-dialog-title">
        <div class="contact-dialog-content">
          <button class="contact-dialog-close" type="button" data-contact-close aria-label="Close message form">&times;</button>
          <p class="contact-dialog-eyebrow">Write a message</p>
          <h4 id="contact-dialog-title">Message Me</h4>
          <form class="contact-form" action="https://formspree.io/f/mwpqwkap" method="POST">
            <label class="visually-hidden" for="contact-name">Your name</label>
            <input id="contact-name" type="text" name="name" placeholder="Your Name" required>
            <label class="visually-hidden" for="contact-email">Your email</label>
            <input id="contact-email" type="email" name="email" placeholder="Your Email" required>
            <label class="visually-hidden" for="contact-message">Your message</label>
            <textarea id="contact-message" name="message" rows="5" placeholder="Your Message" required></textarea>
            <div class="contact-form-actions">
              <button type="submit">Send Message <span aria-hidden="true">&#8599;</span></button>
              <p class="contact-form-status" aria-live="polite"></p>
            </div>
          </form>
        </div>
      </dialog>`);
  }
}

ensureContactSection();

const contactDialog = document.getElementById('contactDialog');
const contactDialogOpeners = document.querySelectorAll('[data-contact-open]');
const contactDialogClosers = document.querySelectorAll('[data-contact-close]');
const contactForm = document.querySelector('.contact-form');
const contactFormStatus = document.querySelector('.contact-form-status');

function closeContactDialog() {
  if (!contactDialog) return;

  if (typeof contactDialog.close === 'function') {
    contactDialog.close();
    return;
  }

  contactDialog.removeAttribute('open');
}

contactDialogOpeners.forEach(opener => {
  opener.addEventListener('click', () => {
    if (!contactDialog) return;

    if (typeof contactDialog.showModal === 'function') {
      contactDialog.showModal();
      return;
    }

    contactDialog.setAttribute('open', '');
  });
});

contactDialogClosers.forEach(closer => {
  closer.addEventListener('click', closeContactDialog);
});

if (contactDialog) {
  contactDialog.addEventListener('click', event => {
    if (event.target === contactDialog) {
      closeContactDialog();
    }
  });
}

if (contactForm) {
  contactForm.addEventListener('submit', async event => {
    event.preventDefault();

    const submitButton = contactForm.querySelector('button[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }

    if (contactFormStatus) {
      contactFormStatus.textContent = 'Sending...';
    }

    try {
      const response = await fetch(contactForm.action, {
        method: 'POST',
        body: new FormData(contactForm),
        headers: { Accept: 'application/json' }
      });

      if (!response.ok) {
        throw new Error('Message request failed');
      }

      contactForm.reset();
      if (contactFormStatus) {
        contactFormStatus.textContent = 'Message sent. Thank you.';
      }
    } catch (error) {
      if (contactFormStatus) {
        contactFormStatus.textContent = 'Could not send it. Please try again.';
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  });
}

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.body.classList.contains('recruiter-mode-active')) {
    setRecruiterMode(false);
  }
});

const fullAboutText = `I'm a Computer Science Engineering student at SRM Institute of Science and Technology, Kattankulathur, specializing in Artificial Intelligence and Machine Learning. I actively build real-world AI systems with end-to-end ownership from data preprocessing to deployment. I began my ML journey through a great book, that is, Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow by Aurélien Géron (O’Reilly), which laid a strong foundation for practical implementation. One of my key projects is an AutoML pipeline designed for classification tasks, featuring model-specific preprocessing (such as scaling and outlier handling), automated feature engineering, and SHAP-based explainability built to simplify model selection without compromising on transparency. I'm also contributing to a research initiative on AI-based network slicing and digital twin modeling for 6G smart mobility, where I work on predicting QoS metrics and optimizing handovers using ML in simulated environments. Previously, I developed an SLA violation prediction system that won 3rd place at Nokia Campus Connect 2025. Alongside AI, I’ve developed this portfolio site using Flask and frontend technologies (HTML, CSS, JS) showcasing my ability to deliver clean, production-ready interfaces with backend logic, all independently built from scratch.`;

function typeParagraphWithMovingCursor(text, element, cursor, speed = 18) {
  element.innerHTML = "";
  cursor.style.display = "inline-block";
  cursor.style.fontSize = "4em";
  cursor.style.color = "white";
  cursor.classList.add("blinking-cursor");
  let i = 0;
  function type() {
    if (i <= text.length) {
      // Insert the blinking vertical line before the next letter
      element.innerHTML = text.slice(0, i) + `<span id="type-cursor-inner" style="font-size:1.6em;color:white;display:inline-block;width:0.6em;" class="blinking-cursor">|</span>`;
      i++;
      setTimeout(type, speed);
    } else {
      // Remove the cursor after typing is done
      element.innerHTML = text;
      cursor.style.display = "none";
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
      para.classList.add("hidden");
      para.innerHTML = "";
      cursor.style.display = "none";
    }
  }
}

const taglineText = "OPERATIONAL MACHINE LEARNING MODELS WITH DIGITAL TWIN INITIATIVES UNDERWAY";
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


// Continuous auto-scroll skills
window.addEventListener("DOMContentLoaded", () => {
  const skillsList = document.getElementById("skills-list");
  if (!skillsList) return;

  // Duplicate list for seamless looping
  const items = Array.from(skillsList.children);
  items.forEach(item => {
    const clone = item.cloneNode(true);
    skillsList.appendChild(clone);
  });

  let position = 0;
  const itemHeight = items[0].offsetHeight || 32; // fallback to 32px if not rendered yet

  function scrollSkills() {
    position += 0.5; // Adjust speed here (smaller = slower, larger = faster)
    if (position >= itemHeight * items.length) {
      position = 0;
    }
    skillsList.style.transform = `translateY(-${position}px)`;
    requestAnimationFrame(scrollSkills);
  }

  scrollSkills();
});

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
function getCarouselVars() {
  const styles = getComputedStyle(document.documentElement);
  return {
    radius: parseInt(styles.getPropertyValue('--carousel-radius')) || 600,
    cardW: parseInt(styles.getPropertyValue('--carousel-card-width')) || 240,
    cardH: parseInt(styles.getPropertyValue('--carousel-card-height')) || 320,
    scaleFactor: parseFloat(styles.getPropertyValue('--carousel-scale-factor')) || 0.5
  };
}
const aboutWorkPanel = document.getElementById('aboutWorkPanel');

const projectCards = Array.from(grid.querySelectorAll('.card.landscape-card')).map(card => ({
  title: card.querySelector('h4').innerHTML,
  desc: card.querySelector('p').innerHTML,
  imgSrc: card.querySelector('.card-img img').src,  // ← ADD THIS LINE
  imgAlt: card.querySelector('.card-img img').alt,   // ← ADD THIS LINE
  link: card.getAttribute('href') // Add project card link
}));

let angle = 0;
let animating = false;
const N = projectCards.length;
const step = 360 / N;
let dragging = false;
let dragStartX = 0;

function animateTo(targetAngle) {
  if (animating) return;
  animating = true;
  const startAngle = angle;
  const duration = 700;
  const startTime = performance.now();

  function animate(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    angle = startAngle + (targetAngle - startAngle) * progress;
    renderCarousel();
    if (progress < 1) {
      requestAnimationFrame(animate);
    } else {
      angle = targetAngle;
      renderCarousel();
      animating = false;
    }
  }

  requestAnimationFrame(animate);
}

function renderCarousel() {
  carouselCardsContainer.innerHTML = '';
  const N = projectCards.length;

  const { radius, cardW, cardH, scaleFactor } = getCarouselVars();

  for (let i = 0; i < N; i++) {
    const card = document.createElement('a');
    card.className = 'carousel-card';
    card.style.width = cardW + 'px';
    card.style.height = cardH + 'px';

    card.innerHTML = `
      <div class="card-img">
        <img src="${projectCards[i].imgSrc}" alt="${projectCards[i].imgAlt}">
      </div>
      <div class="card-content">
        <h4>${projectCards[i].title}</h4>
        <p>${projectCards[i].desc}</p>
      </div>
    `;

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

    card.style.transform = `
      translateX(${x}px)
      translateZ(${z}px)
      translateY(-50%)
      rotateY(${theta}deg)
      scale(${scale.toFixed(2)})
    `;

    // Opacity fade
    const opacity = Math.cos((distance / 180) * (Math.PI / 2));
    card.style.opacity = opacity.toFixed(2);

    // Layering
    card.style.zIndex = String(Math.round(100 - distance));

    // Styling classes
    if (distance < 20) card.classList.add('active');
    else if (distance < 80) card.classList.add('side');
    else if (distance < 160) card.classList.add('far');
    else card.classList.add('hidden');

    carouselCardsContainer.appendChild(card);
  }
}

window.addEventListener('resize', renderCarousel);
window.addEventListener('orientationchange', renderCarousel);
renderCarousel();
showCarousel();

function showCarousel() {
  grid.style.display = 'none';
  carouselContainer.classList.add('active');
  toggleBtn.textContent = 'Expand';
  aboutWorkPanel.classList.remove('expanded');
  aboutWorkPanel.classList.add('minimized');
  renderCarousel();
}

function showGrid() {
  grid.style.display = 'flex';
  carouselContainer.classList.remove('active');
  toggleBtn.textContent = 'Minimize';
  aboutWorkPanel.classList.remove('minimized');
  aboutWorkPanel.classList.add('expanded');
}

toggleBtn.addEventListener('click', () => {
  if (carouselContainer.classList.contains('active')) {
    showGrid();
  } else {
    showCarousel();
  }
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
  const step = 360 / projectCards.length;
  animateTo(angle + step);
  renderCarousel();
});

arrowRight.addEventListener('click', () => {
  const step = 360 / projectCards.length;
  animateTo(angle - step);
  renderCarousel();
});



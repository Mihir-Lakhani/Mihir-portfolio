const fullAboutText = `I'm a Computer Science Engineering student at SRM Institute of Science and Technology, Kattankulathur, specializing in Artificial Intelligence and Machine Learning. I actively build real-world AI systems with end-to-end ownership from data preprocessing to deployment. I began my ML journey through Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow by Aurélien Géron (O’Reilly), which laid a strong foundation for practical implementation. One of my key projects is an AutoML pipeline designed for classification tasks, featuring model-specific preprocessing (such as scaling and outlier handling), automated feature engineering, and SHAP-based explainability built to simplify model selection without compromising on transparency. I'm also contributing to a research initiative on AI-based network slicing and digital twin modeling for 6G smart mobility, where I work on predicting QoS metrics and optimizing handovers using ML in simulated environments. Previously, I developed an SLA violation prediction system that won 3rd place at Nokia Campus Connect 2025. Alongside AI, I’ve developed this portfolio site using Flask and frontend technologies (HTML, CSS, JS) showcasing my ability to deliver clean, production-ready interfaces with backend logic, all independently built from scratch.`;

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

// ...existing code...

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


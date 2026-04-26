document.addEventListener("DOMContentLoaded", () => {
    
    // Page load transition
    const mainContent = document.querySelector('.page-transition');
    if (mainContent) {
        setTimeout(() => {
            mainContent.classList.add('visible');
        }, 100);
    }

    // Ripple effect on buttons
    const buttons = document.querySelectorAll('.btn-primary');
    buttons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            let x = e.clientX - e.target.getBoundingClientRect().left;
            let y = e.clientY - e.target.getBoundingClientRect().top;

            let ripples = document.createElement('span');
            ripples.style.left = x + 'px';
            ripples.style.top = y + 'px';
            ripples.classList.add('ripple');
            this.appendChild(ripples);

            setTimeout(() => {
                ripples.remove();
            }, 600);
        });
    });

    // Subtly animating background particles
    createParticles();
});

function createParticles() {
    const container = document.getElementById('particles-container');
    if (!container) return;

    const numParticles = 15;
    for (let i = 0; i < numParticles; i++) {
        const el = document.createElement('div');
        el.classList.add('particle');
        
        // Random size
        const size = Math.random() * 40 + 20;
        el.style.width = size + 'px';
        el.style.height = size + 'px';
        
        // Use DNA-like icon (fontawesome) or just circles
        if (Math.random() > 0.5) {
            el.innerHTML = '<i class="fa-solid fa-dna particle-icon"></i>';
        } else {
            el.classList.add('particle-blob');
        }

        // Random starting position
        el.style.left = Math.random() * 100 + 'vw';
        el.style.top = Math.random() * 100 + 'vh';
        
        // Random animation duration & delay
        el.style.animationDuration = Math.random() * 20 + 20 + 's';
        el.style.animationDelay = Math.random() * 5 + 's';
        
        container.appendChild(el);
    }
}

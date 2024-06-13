document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    const questions = document.querySelectorAll('form div');

    form.addEventListener('submit', (event) => {
        let allAnswered = true;
        
        questions.forEach((question) => {
            const options = question.querySelectorAll('input[type="radio"]');
            let answered = false;
            options.forEach((option) => {
                if (option.checked) {
                    answered = true;
                }
            });
            if (!answered) {
                allAnswered = false;
                question.style.border = '2px solid red';
            } else {
                question.style.border = 'none';
            }
        });

        if (!allAnswered) {
            event.preventDefault();
            alert('Please answer all questions before submitting.');
        }
    });
});

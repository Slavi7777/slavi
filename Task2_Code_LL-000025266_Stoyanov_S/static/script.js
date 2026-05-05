<script>
function toggleAccessibility() {
    document.body.classList.toggle("high-contrast");
}

document.addEventListener("DOMContentLoaded", function () {

    let email = document.getElementById("email");
    let password = document.getElementById("password");

    let emailError = document.getElementById("emailError");
    let passwordError = document.getElementById("passwordError");

    let emailHint = document.getElementById("emailHint");
    let passwordHint = document.getElementById("passwordHint");

    let emailPattern = /^[\w\.-]+@[\w\.-]+\.\w+$/;

    // ===== EMAIL =====
    email.addEventListener("focus", () => emailHint.style.display = "block");
    email.addEventListener("blur", () => emailHint.style.display = "none");

    email.addEventListener("input", function () {
        let value = this.value;

        if (value.length === 0) {
            emailError.style.display = "none";
            email.style.borderColor = "";
            return;
        }

        emailError.style.display = "block";

        if (!emailPattern.test(value)) {
            emailError.innerHTML = "❌ Invalid email format";
            emailError.style.background = "#b22222";
            email.style.borderColor = "red";
        } else {
            emailError.innerHTML = "✅ Valid email";
            emailError.style.background = "#2e7d32";
            email.style.borderColor = "green";
        }
    });

    // ===== PASSWORD =====
    password.addEventListener("focus", () => passwordHint.style.display = "block");
    password.addEventListener("blur", () => passwordHint.style.display = "none");

    password.addEventListener("input", function () {
        let value = this.value;

        let checks = {
            length: value.length >= 8,
            uppercase: /[A-Z]/.test(value),
            lowercase: /[a-z]/.test(value),
            number: /\d/.test(value),
            special: /[@$!%*?&]/.test(value)
        };

        // ✅ UPDATE CHECKLIST
        for (let key in checks) {
            let item = document.getElementById(key);

            if (item) {
                if (checks[key]) {
                    item.innerHTML = "✅ " + item.textContent.substring(2);
                    item.style.color = "lightgreen";
                } else {
                    item.innerHTML = "❌ " + item.textContent.substring(2);
                    item.style.color = "white";
                }
            }
        }

        if (value.length === 0) {
            passwordError.style.display = "none";
            password.style.borderColor = "";
            return;
        }

        passwordError.style.display = "block";

        if (Object.values(checks).every(Boolean)) {
            passwordError.innerHTML = "✅ Strong password";
            passwordError.style.background = "#2e7d32";
            password.style.borderColor = "green";
        } else {
            passwordError.innerHTML = "❌ Password not strong enough";
            passwordError.style.background = "#b22222";
            password.style.borderColor = "red";
        }
    });

});
</script>

const revealElements = document.querySelectorAll('.reveal');

window.addEventListener('scroll', () => {
    revealElements.forEach(el => {
        const position = el.getBoundingClientRect().top;
        const screenHeight = window.innerHeight;

        if(position < screenHeight - 100){
            el.classList.add('active');
        }
    });
});

<script>
async function fetchAddress() {

    let postcode = document.getElementById("postcode").value.trim();

    if (!postcode) {
        alert("Enter a postcode first");
        return;
    }

    // Format postcode
    postcode = postcode.replace(" ", "").toUpperCase();

    try {
        let response = await fetch(`https://api.postcodes.io/postcodes/${postcode}`);
        let data = await response.json();

        if (data.status !== 200) {
            alert("Invalid postcode");
            return;
        }

        // 🔥 AUTO FILL
        document.getElementById("city").value = data.result.admin_district;
        document.getElementById("county").value = data.result.region;

    } catch (error) {
        alert("Error fetching address");
    }
}
</script>


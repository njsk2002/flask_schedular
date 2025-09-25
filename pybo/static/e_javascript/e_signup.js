 // 이메일 검증 함수 (실시간 및 제출 시)
 function validateEmailField() {
    const emailField = document.getElementById('email');
    const emailMessage = document.getElementById('email-message'); // 이메일 메시지 출력할 요소 추가 필요
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailField.value) {
      emailMessage.textContent = "이메일을 입력하세요.";
      emailMessage.className = "message error";
      emailField.classList.add("input-error");
      emailField.classList.remove("input-success");
      return false;
    }

    if (!emailRegex.test(emailField.value)) {
      emailMessage.textContent = "올바른 이메일 형식이 아닙니다.";
      emailMessage.className = "message error";
      emailField.classList.add("input-error");
      emailField.classList.remove("input-success");
      return false;
    }

    emailMessage.textContent = "사용 가능한 이메일입니다.";
    emailMessage.className = "message success";
    emailField.classList.remove("input-error");
    emailField.classList.add("input-success");
    return true;
  }


  // 비밀번호 및 비밀번호 확인 검증 함수 (실시간 및 제출 시)
  function validatePasswordFields() {
    const pwdField = document.getElementById('password');
    const pwdConfirmField = document.getElementById('password-confirm');
    const pwdMessage = document.getElementById('password-message'); // 비밀번호 메시지 출력할 요소 추가 필요
    const confirmMessage = document.getElementById('password-confirm-message'); // 비밀번호 확인 메시지 요소 추가 필요
    let valid = true;

    if (!pwdField.value) {
      pwdMessage.textContent = "비밀번호를 입력하세요.";
      pwdMessage.className = "message error";
      pwdField.classList.add("input-error");
      pwdField.classList.remove("input-success");
      valid = false;
    } else if (pwdField.value.length < 8) {
      pwdMessage.textContent = "비밀번호는 8자리 이상이어야 합니다.";
      pwdMessage.className = "message error";
      pwdField.classList.add("input-error");
      pwdField.classList.remove("input-success");
      valid = false;
    } else {
      pwdMessage.textContent = "사용 가능한 비밀번호입니다.";
      pwdMessage.className = "message success";
      pwdField.classList.remove("input-error");
      pwdField.classList.add("input-success");
    }

    if (!pwdConfirmField.value) {
      confirmMessage.textContent = "비밀번호 확인을 입력하세요.";
      confirmMessage.className = "message error";
      pwdConfirmField.classList.add("input-error");
      pwdConfirmField.classList.remove("input-success");
      valid = false;
    } else if (pwdField.value !== pwdConfirmField.value) {
      confirmMessage.textContent = "비밀번호가 일치하지 않습니다.";
      confirmMessage.className = "message error";
      pwdConfirmField.classList.add("input-error");
      pwdConfirmField.classList.remove("input-success");
      valid = false;
    } else {
      confirmMessage.textContent = "비밀번호가 일치합니다.";
      confirmMessage.className = "message success";
      pwdConfirmField.classList.remove("input-error");
      pwdConfirmField.classList.add("input-success");
    }

    return valid;
  }


  // 이미지 미리보기
  function previewImage(event, previewId) {
    const preview = document.getElementById(previewId);
    const file = event.target.files[0];

    if (file) {
        const reader = new FileReader();
        reader.onload = function () {
            preview.src = reader.result;
            preview.style.display = "block"; // 이미지 선택 시 보이게 함
        }
        reader.readAsDataURL(file);
    } else {
        preview.src = "";
        preview.style.display = "none"; // 이미지가 선택되지 않으면 숨김
    }
}


// 주소/홈페이지등 인풋값이 고정된것 전송
function enableField(fieldId) {
  document.getElementById(fieldId).removeAttribute('readonly');
}

function enableInputsBeforeSubmit() {
  const inputs = document.querySelectorAll('input[readonly]');
  inputs.forEach(input => input.removeAttribute('readonly'));
}


  // 브라우저에서 안전하게 `onerror` 설정
  document.addEventListener("DOMContentLoaded", function () {
      const preview = document.getElementById("photo-preview");
      
      // 기본 이미지 경로를 자바스크립트 변수에 저장
      const defaultImage = "{{ url_for('static', filename='images/icetech.png') }}";

      preview.onerror = function () {
          this.src = defaultImage;
          this.style.display = "block";
      };
  });

 // 가입 완료시 모달 팝업용
  document.addEventListener("DOMContentLoaded", function () {
    let modal = document.getElementById('signupSuccessModal');
    if (modal) {
        modal.classList.add('show');
        modal.style.display = 'block';

        modal.onclick = function (event) {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        };
    }
});

// 📌 휴대폰 번호 자동 하이픈 추가 + 검증
function formatAndValidatePhoneNumber() {
    const phoneInput = document.getElementById('phone');
    let phoneValue = phoneInput.value.replace(/[^0-9]/g, ''); // 숫자만 입력 가능
    const phoneMessage = document.getElementById('phone-message'); // 메시지 표시용 요소

    if (!phoneMessage) {
        console.error("phone-message 요소가 없습니다.");
        return;
    }

    // 📌 휴대폰 번호 자동 하이픈 추가
    if (phoneValue.length > 3 && phoneValue.length <= 7) {
        phoneValue = phoneValue.slice(0, 3) + '-' + phoneValue.slice(3);
    } else if (phoneValue.length > 7) {
        phoneValue = phoneValue.slice(0, 3) + '-' + phoneValue.slice(3, 7) + '-' + phoneValue.slice(7);
    }
    phoneInput.value = phoneValue;

    // 📌 휴대폰 번호 유효성 검사
    const rawPhoneValue = phoneValue.replace(/-/g, ''); // 하이픈 제거한 숫자만 남기기

    if (!rawPhoneValue) {
        phoneMessage.textContent = "휴대폰 번호를 입력하세요.";
        phoneMessage.className = "message error";
        phoneInput.classList.add("input-error");
        phoneInput.classList.remove("input-success");
        return false;
    }

    if (rawPhoneValue.length < 11 || rawPhoneValue.length > 11) {
        phoneMessage.textContent = "휴대폰 번호는 10~11자리 숫자로 입력해야 합니다.";
        phoneMessage.className = "message error";
        phoneInput.classList.add("input-error");
        phoneInput.classList.remove("input-success");
        return false;
    }

    phoneMessage.textContent = "올바른 휴대폰 번호입니다.";
    phoneMessage.className = "message success";
    phoneInput.classList.remove("input-error");
    phoneInput.classList.add("input-success");
    return true;
}


  // 아이디 중복 체크 (실시간)
  async function checkIdDuplication() {
    const useridField = document.getElementById('userid');
    const idMessage = document.getElementById('id-message');
    const userid = useridField.value.trim();
    if (!userid) {
      idMessage.textContent = "";
      useridField.classList.remove("input-error", "input-success");
      return;
    }
    
    try {
      const response = await fetch('/auth/idcheck', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ userid: userid })
      });
      const result = await response.json();
      if (result.available) {
        idMessage.textContent = result.message;
        idMessage.className = "message success";
        useridField.classList.remove("input-error");
        useridField.classList.add("input-success");
      } else {
        idMessage.textContent = result.message;
        idMessage.className = "message error";
        useridField.classList.remove("input-success");
        useridField.classList.add("input-error");
      }
    } catch (error) {
      console.error('Error during id check:', error);
    }
  }


  // term popup 기능
  function openTermsPopup() {
    const popupWidth = 600;
    const popupHeight = 700;
    const left = (window.innerWidth - popupWidth) / 2;
    const top = (window.innerHeight - popupHeight) / 2;

    window.open(
        "terms",  // Flask 라우트
        "termsPopup",
        `width=${popupWidth},height=${popupHeight},left=${left},top=${top},scrollbars=yes,resizable=yes`
    );
}

document.getElementById('signup-btn').addEventListener('click', function (e) {
    const termsAgree = document.getElementById('terms-agree');
    if (!termsAgree.checked) {
        alert("이용약관에 동의해야 회원가입이 가능합니다.");
        e.preventDefault();
    }
});

  // 📌 실시간 이벤트 리스너 추가
  document.getElementById('email').addEventListener('input', validateEmailField);  
  document.getElementById('phone').addEventListener('input', formatAndValidatePhoneNumber);

  document.getElementById('password').addEventListener('input', validatePasswordFields);
  document.getElementById('password-confirm').addEventListener('input', validatePasswordFields);
  document.getElementById('userid').addEventListener('blur', checkIdDuplication);


  // 회원가입 버튼 눌렸을때  각 요소 체크
  document.getElementById('signup-form').addEventListener('submit', async function(e) {
    e.preventDefault(); // 기본 제출 동작을 먼저 막음

    // 📌 사진 선택 여부 검증
    const photoInput = document.getElementById('photo1');
    if (!photoInput.files || photoInput.files.length === 0) {
        alert("회원 사진을 선택해 주세요.");
        photoInput.focus();
        return;
    }
  
    // 📌 아이디 중복 체크 (최종 확인)
    await checkIdDuplication();
    const idMsg = document.getElementById('id-message').textContent;
    if (idMsg === "이미 존재하는 사용자입니다.") {
        alert("이미 존재하는 아이디입니다.");
        document.getElementById('userid').focus();
        return;
    }
  
    // 📌 이메일 형식 검증
    if (!validateEmailField()) {
        alert("이메일 형식이 올바르지 않습니다.");
        document.getElementById('email').focus();
        return;
    }
  
    // 📌 비밀번호 및 비밀번호 확인 검증
    if (!validatePasswordFields()) {
        alert("비밀번호는 8자리 이상이어야 하며, 비밀번호와 확인이 일치해야 합니다.");
        document.getElementById('password').focus();
        return;
    }

    // 📌 휴대폰 번호 형식 검증
    if (!formatAndValidatePhoneNumber()) {
        alert("휴대폰 번호 형식이 올바르지 않습니다.");
        document.getElementById('phone').focus();
        return;
    }

    // 📌 기타 필수 입력란 검증 (userid, 이름, 휴대폰, 이메일, 회사, 나이)
    const requiredFields = ['userid', 'name', 'phone', 'email', 'company' ];
    for (let i = 0; i < requiredFields.length; i++) {
        const field = document.getElementById(requiredFields[i]);
        if (field && field.value.trim() === '') {
            alert(field.previousElementSibling.textContent + " 항목을 입력해 주세요."); // 해당 label의 텍스트 가져오기
            field.focus();
            return;
        }
    }

    // 📌 모든 검증을 통과한 후 `confirm` 창 띄우기
    if (confirm("회원가입 하시겠습니까?")) {
        e.target.submit(); // 폼 제출 진행
    }
});

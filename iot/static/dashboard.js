let notifiedBookings = new Set();

// ========== UTAMA: Update Status Slot ==========
async function updateSlots() {
  try {
    const res = await fetch("/api/status", { cache: "no-cache" });
    if (!res.ok) {
      console.error("API status response not OK:", res.status);
      return;
    }

    const data = await res.json();
    console.log("API status response:", data);

    const statusMap = {
      "B3": data.v0,
      "A6": data.v1,
      "A3": data.v2
    };

    const bookings = data.bookings || [];
    const expiredBookings = data.expired_bookings || [];
    const currentUser = data.current_user;

    let filledCount = 0;
    let bookingCount = 0;
    let userBooking = null;

    // Notifikasi untuk booking pengguna yang telah selesai (dari server)
    expiredBookings.forEach(expired => {
      if (expired.user_id === currentUser && !notifiedBookings.has(expired.slot_id)) {
        showToast(`Waktu booking habis, segera ke slot parkir Anda di Slot ${expired.slot_id}!`, true);
        notifiedBookings.add(expired.slot_id);
      }
    });

    document.querySelectorAll('.slot').forEach(slot => {
      const id = slot.dataset.id;
      const prevClass = slot.className;
      slot.classList.remove("empty", "filled", "booked", "booked-own");
      slot.title = "";

      const isBooked = bookings.find(b => b.slot_id === id);
      const isFilled = statusMap[id] === "Isi";

      if (isBooked && isBooked.user_id === currentUser) {
        slot.classList.add("booked-own");
        slot.title = `Booking Anda: ${Math.floor(isBooked.duration / 60)} jam ${isBooked.duration % 60} menit`;
        bookingCount++;
        userBooking = isBooked;
      } else if (isBooked) {
        slot.classList.add("booked");
        slot.title = `Sudah dibooked${isBooked.username ? ' oleh ' + isBooked.username : ''}`;
        bookingCount++;
      } else if (isFilled) {
        slot.classList.add("filled");
        slot.title = "Terisi";
        filledCount++;
      } else {
        slot.classList.add("empty");
        slot.title = "Kosong";

        // Deteksi transisi dari booked ke kosong
        if (prevClass.includes("booked") || prevClass.includes("booked-own")) {
          showToast(`Slot ${id} kini kosong (booking selesai)`);
        }
      }

      console.log(`Slot ${id} status: ${slot.className}, booked: ${!!isBooked}, filled: ${isFilled}`);

      // ========== EVENT HANDLER KLIK SLOT ==========
      slot.onclick = () => {
        if (slot.classList.contains("empty")) {
          if (!currentUser) {
            showModal(`Slot ${id} kosong. Login untuk booking?`, (confirmLogin) => {
              if (confirmLogin) window.location.href = "/login";
            });
          } else {
            showBookingForm(id);
          }
        } else if (slot.classList.contains("booked-own")) {
          showModal(`Anda telah booking slot ${id} untuk ${Math.floor(isBooked.duration / 60)} jam ${isBooked.duration % 60} menit. Lepaskan?`, (confirmUnbook) => {
            if (confirmUnbook) {
              const form = document.createElement("form");
              form.method = "POST";
              form.action = `/unbook/${id}`;
              document.body.appendChild(form);
              form.submit();
            }
          });
        }
      };
    });

    // ========== UPDATE INFO TOTAL SLOT ==========
    const totalSlot = document.querySelectorAll('.slot').length;
    const sisaSlot = totalSlot - filledCount - bookingCount;

    document.getElementById("total-slot").textContent = totalSlot;
    document.getElementById("sisa-slot").textContent = sisaSlot;
    document.getElementById("slot-terisi").textContent = filledCount;

    // ========== TAMPILKAN SISA WAKTU ==========
    if (userBooking) {
      updateRemainingTime(userBooking);
    } else {
      document.getElementById("remainingTime").style.display = "none";
      notifiedBookings.clear();
    }

    // ========== TAMPILKAN KEMBALI NOTIFIKASI YANG MASIH AKTIF ==========
    displayActiveNotifications();

  } catch (err) {
    console.error("Gagal ambil status:", err);
  }
}

// ========== TAMPILKAN SISA WAKTU ==========
function updateRemainingTime(booking) {
  const remainingMinutes = booking.remaining_duration;
  const slotId = booking.slot_id;
  const currentUser = booking.user_id;

  if (remainingMinutes <= 0) {
    // Sembunyikan sisa waktu
    document.getElementById("remainingTime").style.display = "none";

    // Cek apakah notifikasi belum ditampilkan untuk slot ini
    if (!notifiedBookings.has(slotId)) {
      // Tampilkan notifikasi
      showToast(`Waktu booking habis, segera ke slot parkir Anda di Slot ${slotId}!`, true);
      notifiedBookings.add(slotId);

      // Kirim request untuk menghapus booking (autounbook)
      const form = document.createElement("form");
      form.method = "POST";
      form.action = `/unbook/${slotId}`;
      document.body.appendChild(form);
      form.submit();
    }
    return;
  }

  const hours = Math.floor(remainingMinutes / 60);
  const minutes = remainingMinutes % 60;
  const timeLeft = `${hours} jam ${minutes} menit`;

  document.getElementById("timeLeft").textContent = timeLeft;
  document.getElementById("remainingTime").style.display = "block";
}

// ========== MODAL KONFIRMASI ==========
function showModal(message, callback) {
  const modal = document.getElementById("customModal");
  const modalText = document.getElementById("modalText");
  const yesBtn = document.getElementById("modalYes");
  const cancelBtn = document.getElementById("modalCancel");
  const bookingForm = document.getElementById("bookingForm");

  modalText.textContent = message;
  bookingForm.style.display = "none";
  modal.style.display = "flex";

  const cleanup = () => {
    modal.style.display = "none";
    yesBtn.onclick = null;
    cancelBtn.onclick = null;
  };

  yesBtn.onclick = () => {
    cleanup();
    callback(true);
  };

  cancelBtn.onclick = () => {
    cleanup();
    callback(false);
  };
}

// ========== FORM BOOKING SLOT ==========
function showBookingForm(slotId) {
  const modal = document.getElementById("customModal");
  const modalText = document.getElementById("modalText");
  const bookingForm = document.getElementById("bookingForm");
  const yesBtn = document.getElementById("modalYes");
  const cancelBtn = document.getElementById("modalCancel");
  const hoursInput = document.getElementById("hours-input");
  const minutesInput = document.getElementById("minutes-input");
  const totalPriceDisplay = document.getElementById("totalPrice");

  modalText.textContent = `Booking Slot ${slotId}`;
  bookingForm.style.display = "block";
  modal.style.display = "flex";

  // Reset input
  hoursInput.value = 0;
  minutesInput.value = 0;

  function updateTotalPrice() {
    const hours = parseInt(hoursInput.value) || 0;
    const minutes = parseInt(minutesInput.value) || 0;
    const totalPrice = (hours * 5000) + (minutes * 830);  // Rp5,000 per jam, Rp830 per menit
    totalPriceDisplay.textContent = `Total: Rp${totalPrice.toLocaleString('id-ID')}`;
  }

  hoursInput.oninput = updateTotalPrice;
  minutesInput.oninput = updateTotalPrice;
  updateTotalPrice();

  const cleanup = () => {
    modal.style.display = "none";
    bookingForm.style.display = "none";
    yesBtn.onclick = null;
    cancelBtn.onclick = null;
    hoursInput.oninput = null;
    minutesInput.oninput = null;
  };

  yesBtn.onclick = () => {
    const hours = parseInt(hoursInput.value) || 0;
    const minutes = parseInt(minutesInput.value) || 0;
    if (hours === 0 && minutes === 0) {
      alert("Durasi minimal 1 menit.");
      return;
    }
    if (hours > 24 || (hours === 24 && minutes > 0)) {
      alert("Durasi maksimal 24 jam.");
      return;
    }
    if (minutes >= 60) {
      alert("Menit harus kurang dari 60.");
      return;
    }

    const form = document.createElement("form");
    form.method = "POST";
    form.action = `/book/${slotId}`;
    form.innerHTML = `
      <input type="hidden" name="hours" value="${hours}">
      <input type="hidden" name="minutes" value="${minutes}">
    `;
    document.body.appendChild(form);
    form.submit();
    cleanup();
  };

  cancelBtn.onclick = () => {
    cleanup();
  };
}

// ========== TOAST NOTIFIKASI ==========
function showToast(message, isImportant = false) {
  // Simpan notifikasi ke sessionStorage
  const notification = {
    message: message,
    isImportant: isImportant,
    timestamp: Date.now(),
    duration: isImportant ? 10000 : 5000 // 10 detik untuk notifikasi penting, 5 detik untuk biasa
  };

  // Simpan hanya notifikasi terbaru per slot untuk menghindari duplikat
  const slotIdMatch = message.match(/Slot (\w+)/);
  const slotId = slotIdMatch ? slotIdMatch[1] : 'general';
  sessionStorage.setItem(`notification_${slotId}`, JSON.stringify(notification));

  // Tampilkan notifikasi
  displayNotification(notification);
}

// Fungsi untuk menampilkan notifikasi
function displayNotification(notification) {
  const toast = document.createElement("div");
  toast.textContent = notification.message;
  toast.className = `toast-message ${notification.isImportant ? 'important' : ''}`;
  document.body.appendChild(toast);

  setTimeout(() => toast.style.opacity = 1, 100);
  setTimeout(() => {
    toast.style.opacity = 0;
    setTimeout(() => toast.remove(), 500);
  }, notification.duration);
}

// Fungsi untuk menampilkan kembali notifikasi aktif
function displayActiveNotifications() {
  // Bersihkan notifikasi yang sudah kedaluwarsa
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key.startsWith('notification_')) {
      const notification = JSON.parse(sessionStorage.getItem(key));
      const elapsed = Date.now() - notification.timestamp;
      if (elapsed >= notification.duration) {
        sessionStorage.removeItem(key);
      }
    }
  }

  // Tampilkan kembali notifikasi yang masih aktif
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key.startsWith('notification_')) {
      const notification = JSON.parse(sessionStorage.getItem(key));
      const elapsed = Date.now() - notification.timestamp;
      if (elapsed < notification.duration) {
        // Hanya tampilkan jika toast belum ada di DOM
        const existingToast = Array.from(document.querySelectorAll('.toast-message'))
          .find(toast => toast.textContent === notification.message);
        if (!existingToast) {
          displayNotification(notification);
        }
      }
    }
  }
}

// ========== AUTO REFRESH TIAP 1 DETIK ==========
setInterval(updateSlots, 1000);
window.onload = updateSlots;

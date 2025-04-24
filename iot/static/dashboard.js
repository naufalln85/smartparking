let notifiedBookings = new Set();
let currentSlot = 0;
let isPopupVisible = false;

async function updateSlots() {
  try {
    const res = await fetch("/api/status", { cache: "no-cache" });
    if (!res.ok) {
      console.error("API status response not OK:", res.status);
      return;
    }
    const data = await res.json();
    console.log("API status response:", data);

    const slotMap = {
      "B3": { occupied: data.slot1.occupied, booked: data.slot1.booked },
      "A6": { occupied: data.slot2.occupied, booked: data.slot2.booked },
      "A3": { occupied: data.slot3.occupied, booked: data.slot3.booked }
    };

    const bookings = data.bookings || [];
    const expiredBookings = data.expired_bookings || [];
    const currentUser = data.current_user;

    // Notifikasi untuk booking yang telah selesai
    expiredBookings.forEach(expired => {
      if (expired.user_id === currentUser && !notifiedBookings.has(expired.slot_id)) {
        showToast(`Waktu booking habis, segera ke slot parkir Anda di Slot ${expired.slot_id}!`, true);
        notifiedBookings.add(expired.slot_id);
      }
    });

    let filledCount = 0;
    let bookingCount = 0;
    let userBooking = null;

    document.querySelectorAll('.slot').forEach(slot => {
      const id = slot.dataset.id;
      const prevClass = slot.className;
      slot.classList.remove("empty", "filled", "booked", "booked-own");
      slot.title = "";

      const slotData = slotMap[id] || { occupied: false, booked: false };
      const isBooked = bookings.find(b => b.slot_id === id);
      const isOccupied = slotData.occupied === true || slotData.occupied === "true" || slotData.occupied === 1 || slotData.occupied === "1";
      const isBookedThingsBoard = slotData.booked === true || slotData.booked === "true" || slotData.booked === 1 || slotData.booked === "1";

      if (isBooked && isBooked.user_id === currentUser) {
        slot.classList.add("booked-own");
        slot.title = `Booking Anda: ${Math.floor(isBooked.duration / 60)} jam ${isBooked.duration % 60} menit`;
        bookingCount++;
        userBooking = isBooked;
      } else if (isBooked || isBookedThingsBoard) {
        slot.classList.add("booked");
        slot.title = `Sudah dibooked${isBooked && isBooked.username ? ' oleh ' + isBooked.username : ''}`;
        bookingCount++;
      } else if (isOccupied) {
        slot.classList.add("filled");
        slot.title = "Terisi";
        filledCount++;
      } else {
        slot.classList.add("empty");
        slot.title = "Kosong";
        if (prevClass.includes("booked") || prevClass.includes("booked-own")) {
          showToast(`Slot ${id} kini kosong (booking selesai)`);
        }
      }

      // Pop-up untuk booked dan occupied
      if (!isPopupVisible && (isBooked || isBookedThingsBoard) && isOccupied && (!isBooked || isBooked.user_id === currentUser)) {
        currentSlot = id === "B3" ? 1 : id === "A6" ? 2 : 3;
        document.getElementById("popup").style.display = "block";
        isPopupVisible = true;
        console.log(`Pop-up shown for Slot ${id}`);
      }

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
          showModal(`Anda telah booking slot ${id}. Lepaskan?`, (confirmUnbook) => {
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

    // Update summary
    const totalSlot = document.querySelectorAll('.slot').length;
    const sisaSlot = totalSlot - filledCount - bookingCount;
    document.getElementById("total-slot").textContent = totalSlot;
    document.getElementById("sisa-slot").textContent = sisaSlot;
    document.getElementById("slot-terisi").textContent = filledCount;

    // Update sisa waktu
    if (userBooking) {
      updateRemainingTime(userBooking);
    } else {
      document.getElementById("remainingTime").style.display = "none";
      notifiedBookings.clear();
    }

    displayActiveNotifications();
  } catch (err) {
    console.error("Gagal ambil status:", err);
  }
}

function updateRemainingTime(booking) {
  const remainingMinutes = booking.remaining_duration;
  const slotId = booking.slot_id;
  if (remainingMinutes <= 0) {
    document.getElementById("remainingTime").style.display = "none";
    if (!notifiedBookings.has(slotId)) {
      showToast(`Waktu booking habis, segera ke slot parkir Anda di Slot ${slotId}!`, true);
      notifiedBookings.add(slotId);
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
  document.getElementById("timeLeft").textContent = `${hours} jam ${minutes} menit`;
  document.getElementById("remainingTime").style.display = "block";
}

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
  yesBtn.onclick = () => { cleanup(); callback(true); };
  cancelBtn.onclick = () => { cleanup(); callback(false); };
}

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
  hoursInput.value = 0;
  minutesInput.value = 0;
  function updateTotalPrice() {
    const hours = parseInt(hoursInput.value) || 0;
    const minutes = parseInt(minutesInput.value) || 0;
    const totalPrice = (hours * 5000) + (minutes * 830);
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
  cancelBtn.onclick = () => { cleanup(); };
}

function confirmSlot(slot, confirm) {
  fetch(`/api/confirm_slot/${slot}/${confirm}`, {
    method: 'POST'
  })
  .then(response => response.json())
  .then(data => {
    console.log(data.message);
    document.getElementById("popup").style.display = "none";
    isPopupVisible = false;
    sessionStorage.setItem('notification', `Slot ${slot} confirmation: ${confirm}`);
    showNotification();
  })
  .catch(error => console.error("Error confirming slot:", error));
}

function showToast(message, isImportant = false) {
  const notification = {
    message: message,
    isImportant: isImportant,
    timestamp: Date.now(),
    duration: isImportant ? 10000 : 5000
  };
  const slotIdMatch = message.match(/Slot (\w+)/);
  const slotId = slotIdMatch ? slotIdMatch[1] : 'general';
  sessionStorage.setItem(`notification_${slotId}`, JSON.stringify(notification));
  displayNotification(notification);
}

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

function displayActiveNotifications() {
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key.startsWith('notification_')) {
      const notification = JSON.parse(sessionStorage.getItem(key));
      const elapsed = Date.now() - notification.timestamp;
      if (elapsed >= notification.duration) {
        sessionStorage.removeItem(key);
      } else if (!document.querySelector(`.toast-message[data-message="${notification.message}"]`)) {
        displayNotification(notification);
      }
    }
  }
}

function showNotification() {
  let notification = sessionStorage.getItem('notification');
  if (notification) {
    alert(notification);
    sessionStorage.removeItem('notification');
  }
}

setInterval(updateSlots, 1000);
window.onload = updateSlots;

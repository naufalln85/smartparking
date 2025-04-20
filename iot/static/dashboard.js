async function updateSlots() {
  try {
    const res = await fetch("/api/status", {
      cache: "no-cache"
    });
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
    const currentUser = data.current_user;

    let filledCount = 0;
    let bookingCount = 0;
    let userBooking = null;

    document.querySelectorAll('.slot').forEach(slot => {
      const id = slot.dataset.id;
      slot.classList.remove("empty", "filled", "booked", "booked-own");
      slot.title = "";

      const isBooked = bookings.find(b => b.slot_id === id);
      const isFilled = statusMap[id] === "Isi";

      if (isBooked && isBooked.user_id === currentUser) {
        slot.classList.add("booked-own");
        slot.title = `Booking Anda: ${isBooked.start_time}`;
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
      }

      console.log(`Slot ${id} status: ${slot.className}, booked: ${!!isBooked}, filled: ${isFilled}`);

      slot.onclick = () => {
        if (slot.classList.contains("empty")) {
          if (!currentUser) {
            showModal(`Slot ${id} kosong. Login untuk booking?`, (confirmLogin) => {
              if (confirmLogin) {
                window.location.href = "/login";
              }
            });
          } else {
            showBookingForm(id);
          }
        } else if (slot.classList.contains("booked-own")) {
          showModal(`Anda telah booking slot ${id} pada ${isBooked.start_time}. Lepaskan?`, (confirmUnbook) => {
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

    const totalSlot = document.querySelectorAll('.slot').length;
    const sisaSlot = totalSlot - filledCount - bookingCount;

    document.getElementById("total-slot").textContent = totalSlot;
    document.getElementById("sisa-slot").textContent = sisaSlot;
    document.getElementById("slot-terisi").textContent = filledCount;

    // Update remaining time
    if (userBooking) {
      updateRemainingTime(userBooking.start_time);
    } else {
      const remainingTimeDiv = document.getElementById("remainingTime");
      remainingTimeDiv.style.display = "none";
    }

  } catch (err) {
    console.error("Gagal ambil status:", err);
  }
}

function updateRemainingTime(startTime) {
  const start = new Date(startTime);
  const now = new Date();
  const diffMs = start - now;
  if (diffMs <= 0) {
    document.getElementById("remainingTime").style.display = "none";
    console.log("Booking expired, hiding remaining time");
    return;
  }

  const hours = Math.floor(diffMs / 3600000);
  const minutes = Math.floor((diffMs % 3600000) / 60000);
  const timeLeft = `${hours} jam ${minutes} menit`;
  document.getElementById("timeLeft").textContent = timeLeft;
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

  yesBtn.onclick = () => {
    console.log("Tombol Ya diklik di showModal");
    cleanup();
    callback(true);
  };

  cancelBtn.onclick = () => {
    console.log("Tombol Batal diklik di showModal");
    cleanup();
    callback(false);
  };
}

function showBookingForm(slotId) {
  try {
    console.log(`Menampilkan form booking untuk slot ${slotId}`);
    const modal = document.getElementById("customModal");
    const modalText = document.getElementById("modalText");
    const bookingForm = document.getElementById("bookingForm");
    const yesBtn = document.getElementById("modalYes");
    const cancelBtn = document.getElementById("modalCancel");
    const startTimeInput = document.getElementById("flatpickr-input");
    const totalPriceDisplay = document.getElementById("totalPrice");

    modalText.textContent = `Booking Slot ${slotId}`;
    bookingForm.style.display = "block";
    modal.style.display = "flex";

    const now = new Date();
    console.log("Setting Flatpickr minDate to:", now.toISOString());
    const flatpickrInstance = flatpickr(startTimeInput, {
      enableTime: true,
      dateFormat: "Y-m-d H:i",
      minDate: now,
      defaultDate: now,
      time_24hr: true,
      onChange: function(selectedDates, dateStr) {
        console.log("Waktu dipilih:", dateStr);
        updateTotalPrice();
      },
      onOpen: function() {
        console.log("Flatpickr dibuka");
      },
      onClose: function() {
        console.log("Flatpickr ditutup");
      }
    });

    function updateTotalPrice() {
      try {
        const start = new Date(startTimeInput.value);
        if (isNaN(start.getTime())) {
          console.error("Invalid start time:", startTimeInput.value);
          totalPriceDisplay.textContent = "Total: Rp0";
          return;
        }
        const diffHours = (start - now) / 3600000;
        const durationHours = diffHours < 1 ? 1 : Math.ceil(diffHours); // Minimum 1 hour, ceiling for more
        const totalPrice = durationHours * 5000;
        totalPriceDisplay.textContent = `Total: Rp${totalPrice.toLocaleString('id-ID')}`;
        console.log(`Waktu: ${startTimeInput.value}, Durasi: ${durationHours} jam, Total: Rp${totalPrice}`);
      } catch (e) {
        console.error("Error in updateTotalPrice:", e);
        totalPriceDisplay.textContent = "Total: Rp0";
      }
    }

    updateTotalPrice();

    const cleanup = () => {
      console.log("Membersihkan form booking");
      modal.style.display = "none";
      bookingForm.style.display = "none";
      yesBtn.onclick = null;
      cancelBtn.onclick = null;
      flatpickrInstance.destroy();
    };

    yesBtn.onclick = () => {
      console.log(`Tombol Ya diklik untuk booking slot ${slotId}, waktu: ${startTimeInput.value}`);
      if (startTimeInput.value) {
        const form = document.createElement("form");
        form.method = "POST";
        form.action = `/book/${slotId}`;
        form.innerHTML = `
          <input type="hidden" name="start_time" value="${startTimeInput.value}">
        `;
        console.log(`Mengirim form ke: ${form.action}, data: start_time=${startTimeInput.value}`);
        document.body.appendChild(form);
        form.submit();
        cleanup();
      } else {
        alert("Harap isi waktu penempatan.");
      }
    };

    cancelBtn.onclick = () => {
      console.log("Tombol Batal diklik untuk booking");
      cleanup();
    };

    console.log("Event listener tombol Ya dan Batal diatur");
  } catch (e) {
    console.error("Error in showBookingForm:", e);
  }
}

window.addEventListener("load", () => {
  setTimeout(() => {
    const loading = document.getElementById("loadingScreen");
    loading.style.opacity = 0;
    setTimeout(() => {
      loading.style.display = "none";
    }, 500);
  }, 1500);
});

setInterval(updateSlots, 2000);
window.onload = updateSlots;

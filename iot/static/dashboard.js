async function updateSlots() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    const statusMap = {
      "B3": data.v0,
      "A6": data.v1,
      "A3": data.v2
    };

    const bookings = data.bookings || [];
    const currentUser = data.current_user;

    let filledCount = 0;
    let bookingCount = 0;

    document.querySelectorAll('.slot').forEach(slot => {
      const id = slot.dataset.id;
      slot.classList.remove("empty", "filled", "booked", "booked-own");
      slot.title = "";

      const isBooked = bookings.find(b => b.slot_id === id);
      const isFilled = statusMap[id] === "Isi";

      if (isBooked && isBooked.user_id === currentUser) {
        slot.classList.add("booked-own");
        slot.title = "Booking Anda";
        bookingCount++;
      } else if (isBooked) {
        slot.classList.add("booked");
        slot.title = "Sudah dibooking";
        if (isBooked.username) {
          slot.title += " oleh " + isBooked.username;
        }
        bookingCount++;
      } else if (isFilled) {
        slot.classList.add("filled");
        slot.title = "Terisi";
        filledCount++;
      } else {
        slot.classList.add("empty");
        slot.title = "Kosong";
      }

      slot.onclick = () => {
        if (slot.classList.contains("empty")) {
          if (!currentUser) {
            showModal(`Slot ${id} kosong. Login untuk booking?`, (confirmLogin) => {
              if (confirmLogin) {
                window.location.href = "/login";
              }
            });
          } else {
            showModal(`Ingin booking slot ${id}?`, (confirmBook) => {
              if (confirmBook) {
                const form = document.createElement("form");
                form.method = "POST";
                form.action = `/book/${id}`;
                document.body.appendChild(form);
                form.submit();
              }
            });
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

    const totalSlot = document.querySelectorAll('.slot').length;
    const sisaSlot = totalSlot - filledCount - bookingCount;

    document.getElementById("total-slot").textContent = totalSlot;
    document.getElementById("sisa-slot").textContent = sisaSlot;
    document.getElementById("slot-terisi").textContent = filledCount;

  } catch (err) {
    console.error("Gagal ambil status:", err);
  }
}

function showModal(message, callback) {
  const modal = document.getElementById("customModal");
  const modalText = document.getElementById("modalText");
  const yesBtn = document.getElementById("modalYes");
  const cancelBtn = document.getElementById("modalCancel");

  modalText.textContent = message;
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

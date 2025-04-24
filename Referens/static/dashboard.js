let currentSlot = 0;
let isPopupVisible = false;

function refresh() {
    fetch('/api/parking_status')
        .then(response => response.json())
        .then(data => {
            // Log data untuk debugging
            console.log("Parking Status (Raw Data):", data);

            // Log tipe data dan nilai untuk debugging
            console.log("Slot 1 - occupied type:", typeof data.slot1.occupied, "value:", data.slot1.occupied);
            console.log("Slot 1 - booked type:", typeof data.slot1.booked, "value:", data.slot1.booked);
            console.log("Slot 2 - occupied type:", typeof data.slot2.occupied, "value:", data.slot2.occupied);
            console.log("Slot 2 - booked type:", typeof data.slot2.booked, "value:", data.slot2.booked);
            console.log("Slot 3 - occupied type:", typeof data.slot3.occupied, "value:", data.slot3.occupied);
            console.log("Slot 3 - booked type:", typeof data.slot3.booked, "value:", data.slot3.booked);

            // Update Slot 1
            document.getElementById("slot1_distance").innerText = parseFloat(data.slot1.distance).toFixed(1);
            let slot1Occupied = data.slot1.occupied === true || data.slot1.occupied === "true" || data.slot1.occupied === 1 || data.slot1.occupied === "1";
            let slot1Booked = data.slot1.booked === true || data.slot1.booked === "true" || data.slot1.booked === 1 || data.slot1.booked === "1";
            console.log("Slot 1 - Occupied (parsed):", slot1Occupied, "Booked (parsed):", slot1Booked, "Distance:", data.slot1.distance);
            document.getElementById("slot1_status").innerText = (slot1Occupied || slot1Booked) ? "Occupied" : "Empty";
            document.getElementById("slot1_status").className = (slot1Occupied || slot1Booked) ? "occupied" : "empty";
            document.getElementById("slot1_booked").innerText = slot1Booked ? "Yes" : "No";

            // Update Slot 2
            document.getElementById("slot2_distance").innerText = parseFloat(data.slot2.distance).toFixed(1);
            let slot2Occupied = data.slot2.occupied === true || data.slot2.occupied === "true" || data.slot2.occupied === 1 || data.slot2.occupied === "1";
            let slot2Booked = data.slot2.booked === true || data.slot2.booked === "true" || data.slot2.booked === 1 || data.slot2.booked === "1";
            console.log("Slot 2 - Occupied (parsed):", slot2Occupied, "Booked (parsed):", slot2Booked, "Distance:", data.slot2.distance);
            document.getElementById("slot2_status").innerText = (slot2Occupied || slot2Booked) ? "Occupied" : "Empty";
            document.getElementById("slot2_status").className = (slot2Occupied || slot2Booked) ? "occupied" : "empty";
            document.getElementById("slot2_booked").innerText = slot2Booked ? "Yes" : "No";

            // Update Slot 3
            document.getElementById("slot3_distance").innerText = parseFloat(data.slot3.distance).toFixed(1);
            let slot3Occupied = data.slot3.occupied === true || data.slot3.occupied === "true" || data.slot3.occupied === 1 || data.slot3.occupied === "1";
            let slot3Booked = data.slot3.booked === true || data.slot3.booked === "true" || data.slot3.booked === 1 || data.slot3.booked === "1";
            console.log("Slot 3 - Occupied (parsed):", slot3Occupied, "Booked (parsed):", slot3Booked, "Distance:", data.slot3.distance);
            document.getElementById("slot3_status").innerText = (slot3Occupied || slot3Booked) ? "Occupied" : "Empty";
            document.getElementById("slot3_status").className = (slot3Occupied || slot3Booked) ? "occupied" : "empty";
            document.getElementById("slot3_booked").innerText = slot3Booked ? "Yes" : "No";

            // Tampilkan pop-up jika slot dipesan dan terdeteksi benda
            if (!isPopupVisible) {
                if (slot1Booked && slot1Occupied) {
                    currentSlot = 1;
                    document.getElementById("popup").style.display = "block";
                    isPopupVisible = true;
                    console.log("Pop-up shown for Slot 1", { booked: slot1Booked, occupied: slot1Occupied });
                } else if (slot2Booked && slot2Occupied) {
                    currentSlot = 2;
                    document.getElementById("popup").style.display = "block";
                    isPopupVisible = true;
                    console.log("Pop-up shown for Slot 2", { booked: slot2Booked, occupied: slot2Occupied });
                } else if (slot3Booked && slot3Occupied) {
                    currentSlot = 3;
                    document.getElementById("popup").style.display = "block";
                    isPopupVisible = true;
                    console.log("Pop-up shown for Slot 3", { booked: slot3Booked, occupied: slot3Occupied });
                } else {
                    console.log("Pop-up not shown", {
                        slot1: { booked: slot1Booked, occupied: slot1Occupied },
                        slot2: { booked: slot2Booked, occupied: slot2Occupied },
                        slot3: { booked: slot3Booked, occupied: slot3Occupied }
                    });
                }
            }
        })
        .catch(error => console.error("Error fetching data:", error));
}

function bookSlot(slot) {
    fetch(`/api/book_slot/${slot}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log(data.message);
        sessionStorage.setItem('notification', `Slot ${slot} booked`);
        showNotification();
    })
    .catch(error => console.error("Error booking slot:", error));
}

function unbookSlot(slot) {
    fetch(`/api/unbook_slot/${slot}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log(data.message);
        sessionStorage.setItem('notification', `Slot ${slot} unbooked`);
        showNotification();
    })
    .catch(error => console.error("Error unbooking slot:", error));
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

function controlLamp(slot, state) {
    fetch(`/api/control_lamp/${slot}/${state}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => console.log(data.message))
    .catch(error => console.error("Error controlling lamp:", error));
}

function showNotification() {
    let notification = sessionStorage.getItem('notification');
    if (notification) {
        alert(notification);
        sessionStorage.removeItem('notification');
    }
}

// Ambil data setiap 1 detik
refresh();
setInterval(refresh, 1000);
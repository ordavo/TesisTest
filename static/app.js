document.getElementById("formTarjeta").addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);

    const response = await fetch("/agregar_tarjeta", {
        method: "POST",
        body: formData
    });

    const data = await response.json();
    const mensajeDiv = document.getElementById("mensaje");

    if (data.mensaje) {
        mensajeDiv.textContent = data.mensaje;
        mensajeDiv.style.color = "green";
    } else {
        mensajeDiv.textContent = "Error: " + data.error;
        mensajeDiv.style.color = "red";
    }
});

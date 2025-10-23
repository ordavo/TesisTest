// 📂 routes/usuarios.js
const express = require('express');
const router = express.Router();
const sql = require('mssql');

// Configura tu conexión
const config = {
  user: 'sa',
  password: 'Guadual1t0',
  server: 'localhost',
  database: 'DESKTOP-UOJSRMF',
  options: { trustServerCertificate: true }
};
// 📂 routes/usuarios.js
router.post('/add', async (req, res) => {
  const { idUsuario, nombre, correo } = req.body;
  try {
    await sql.connect(config);
    await sql.query`
      INSERT INTO Usuarios (IdUsuario, Nombre, Correo)
      VALUES (${idUsuario}, ${nombre}, ${correo})
    `;
    res.json({ message: 'Usuario agregado correctamente' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error al agregar el usuario' });
  }
});

// ✅ Ruta para obtener el siguiente ID disponible
router.get('/next-id', async (req, res) => {
  try {
    await sql.connect(config);
    const result = await sql.query`SELECT ISNULL(MAX(IdUsuario), 0) + 1 AS NextId FROM Usuarios`;
    res.json({ nextId: result.recordset[0].NextId });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error al obtener el siguiente ID' });
  }
});

module.exports = router;

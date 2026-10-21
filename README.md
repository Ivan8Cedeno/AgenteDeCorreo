# Agente de Correo

Este proyecto implementa un agente automatizado basado en el diagrama que revisa la bandeja de entrada, identifica correo spam, prepara borradores para mensajes comunes y envía una alerta urgente por WhatsApp.

## Flujo

1. Lee mensajes de Gmail.
2. Clasifica cada correo como spam, común o urgente.
3. Si es spam, lo envía a la carpeta de spam.
4. Si es un mensaje común, genera un borrador automático.
5. Si es urgente, crea un borrador y envía una notificación a WhatsApp.

## Requisitos

- Python 3.11+
- Credenciales de Gmail con la API habilitada.
- Clave API de OpenAI o Gemini opcional para resumen avanzado.
- Cuenta Twilio opcional para WhatsApp.

## Instalación

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

## Ejecución

```bash
python app/main.py
```

## Variables de entorno

Verifica el archivo `.env.example` para las variables disponibles.

## Modo demo

Por defecto, el proyecto corre en modo demo sin credenciales: genera mensajes de ejemplo para probar la lógica del agente.

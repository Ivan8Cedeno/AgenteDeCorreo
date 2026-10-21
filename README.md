# Agente de Correo

Este proyecto implementa un agente automatizado basado en el diagrama que revisa la bandeja de entrada, identifica correo spam, prepara borradores para mensajes comunes y envía una alerta urgente por WhatsApp.

## Flujo

1. Lee hasta 3 mensajes de la bandeja de entrada de Gmail.
2. Clasifica cada correo como spam, común o urgente.
3. Si es spam, lo mueve a la carpeta Spam de Gmail.
4. Si es común o urgente, guarda una respuesta como borrador en Gmail; no la envía.
5. Si es urgente, también genera una alerta por WhatsApp cuando Twilio está configurado; de lo contrario, la simula.
6. En el simulador de WhatsApp, el usuario puede pedir que se marquen como leídos todos los mensajes no leídos de la bandeja. El agente consulta la cantidad y requiere confirmación antes de modificar Gmail.
7. También se puede pedir que destaque un correo por asunto o remitente. El agente busca entre los 50 mensajes más recientes de la bandeja, pide confirmación si encuentra una coincidencia única y no modifica nada si hay varios resultados o ninguno.

Para operar sobre Gmail, configura las credenciales OAuth y autoriza el permiso de modificación solicitado por Google. Si la autorización guardada no tiene ese permiso, vuelve a autorizar la cuenta. La ejecución normal procesa la bandeja real cuando `DEMO_MODE=false`; en modo demo no modifica Gmail.

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

# Immediate Action Items for Tijmen

**Objective:** Stand up the Linode "Post Office" to enable cross-machine communication.

- [V] Log into Linode and spin up a basic Ubuntu 24.04 (or 22.04) LTS Nanode.
- [V] SSH into the new server.
- [V] Run system updates: `sudo apt update && sudo apt upgrade -y`.
- [V] Install MQTT Broker: `sudo apt install mosquitto mosquitto-clients -y`.
- [ ] Secure the Broker:
    - Run `sudo mosquitto_passwd -c /etc/mosquitto/passwd branch_worker` (create a password).
    - Edit `/etc/mosquitto/conf.d/default.conf`:
```text
      allow_anonymous false
      password_file /etc/mosquitto/passwd
      listener 1883
      ```
    - Restart the service: `sudo systemctl restart mosquitto`.
- [V] Configure UFW (Firewall): `sudo ufw allow 1883` and `sudo ufw enable`.
- [V] Note down the Linode IP address and the MQTT password securely.
- [V] Create the `ai-agency-workspace` folder on your local machine and copy these `.md` files into a `docs/` directory.

Note we called it TheOffice
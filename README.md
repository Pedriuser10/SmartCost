# SmartCost - Costos Gastronómicos

## El Problema
un entorno de gestión de pequeño restaurante abrumado por el caos de los cálculos manuales, planillas de Excel complejas y la presión del tiempo.

## La Solución
SmartCost es una aplicación desarrollada en Python utilizando Kivy y KivyMD. Permite a los usuarios registrar insumos, armar recetas de forma dinámica y calcular el costo real y margen de ganancia de sus platos mediante una interfaz móvil navegable.

## Tecnologías Utilizadas
* Python 3
* Kivy 2.3.0
* KivyMD 1.2.0
* SQLite3 (Base de datos local)

## Instalación y Uso
1. Clonar el repositorio.
2. Instalar las dependencias listadas en el archivo requirements:
   pip install -r requirements.txt
3. Ejecutar la aplicación desde la terminal:
   python main.py

## Estructura del Prototipo (Evaluación RA1)
* **Navegación:** Uso de ScreenManager, MDFloatLayout y MDBoxLayout.
* **Componentes Dinámicos:** Implementación de MDDialog, MDDropdownMenu y MDTextField funcionales en la gestión de recetas.
* **POO:** Clases modulares reutilizables para las tarjetas de interfaz (ModuleCard, DishCard).

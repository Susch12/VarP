#!/usr/bin/env python3
"""
Script de validación para Fase 1.2: Parser y Distribuciones

Prueba que el parser y el generador de distribuciones funcionan correctamente.
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.model_parser import parse_model_file
from src.common.distributions import DistributionGenerator


def main():
    print("=" * 60)
    print("VALIDACIÓN FASE 1.2: Parser y Distribuciones")
    print("=" * 60)
    print()

    # ========================================
    # Test 1: Parser de Modelo
    # ========================================
    print("📝 Test 1: Parseando modelo de ejemplo...")
    try:
        modelo = parse_model_file('modelos/ejemplo_simple.ini')
        print(f"✅ Modelo parseado exitosamente: {modelo.nombre} v{modelo.version}")
        print(f"   - Descripción: {modelo.descripcion}")
        print(f"   - Variables: {len(modelo.variables)}")
        for var in modelo.variables:
            print(f"     • {var.nombre}: {var.tipo}, {var.distribucion}, {var.parametros}")
        print(f"   - Función: {modelo.tipo_funcion} = '{modelo.expresion}'")
        print(f"   - Escenarios: {modelo.numero_escenarios}")
        print(f"   - Semilla: {modelo.semilla_aleatoria}")
        print()
    except Exception as e:
        print(f"❌ Error parseando modelo: {e}")
        return 1

    # ========================================
    # Test 2: Generador de Distribuciones
    # ========================================
    print("🎲 Test 2: Generador de distribuciones...")
    try:
        gen = DistributionGenerator(seed=42)

        # Test distribución normal
        print("   Testing distribución Normal...")
        valores_normal = gen.generate_batch('normal', {'media': 0, 'std': 1}, 100)
        print(f"   ✅ Normal generada: media={valores_normal.mean():.3f}, std={valores_normal.std():.3f}")

        # Test distribución uniforme
        print("   Testing distribución Uniforme...")
        valores_uniform = gen.generate_batch('uniform', {'min': 0, 'max': 10}, 100)
        print(f"   ✅ Uniforme generada: min={valores_uniform.min():.3f}, max={valores_uniform.max():.3f}")

        # Test distribución exponencial
        print("   Testing distribución Exponencial...")
        valores_exp = gen.generate_batch('exponential', {'lambda': 2.0}, 100)
        print(f"   ✅ Exponencial generada: media={valores_exp.mean():.3f} (esperada ~0.5)")
        print()
    except Exception as e:
        print(f"❌ Error generando distribuciones: {e}")
        return 1

    # ========================================
    # Test 3: Integración Parser + Distribuciones
    # ========================================
    print("🔗 Test 3: Integración Parser + Distribuciones...")
    try:
        # Generar un escenario usando el modelo parseado
        gen = DistributionGenerator(seed=modelo.semilla_aleatoria)

        print(f"   Generando escenario para '{modelo.nombre}':")
        escenario = {}
        for var in modelo.variables:
            valor = gen.generate(var.distribucion, var.parametros, var.tipo)
            escenario[var.nombre] = valor
            print(f"     • {var.nombre} = {valor:.4f}")

        # Evaluar expresión (simplificado para este test)
        print(f"   Expresión: {modelo.expresion}")
        resultado = eval(modelo.expresion, {"__builtins__": {}}, escenario)
        print(f"   Resultado: {resultado:.4f}")
        print()
        print("   ✅ Integración exitosa!")
        print()
    except Exception as e:
        print(f"❌ Error en integración: {e}")
        return 1

    # ========================================
    # Resumen
    # ========================================
    print("=" * 60)
    print("✅ FASE 1.2 COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    print()
    print("Componentes validados:")
    print("  ✅ Parser de archivos .ini")
    print("  ✅ Generador de distribuciones (Normal, Uniforme, Exponencial)")
    print("  ✅ Integración Parser + Distribuciones")
    print()
    print("Próximo paso: Fase 1.3 - Productor Básico")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())

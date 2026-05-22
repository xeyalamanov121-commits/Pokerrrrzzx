import { Text, View, StyleSheet, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";

export default function Index() {
  const router = useRouter();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>TEXAS HOLD'EM</Text>
      <Text style={styles.subtitle}>Premium 3D Poker 🎰</Text>
      
      <TouchableOpacity style={styles.button} onPress={() => router.push("/poker")}>
        <Text style={styles.buttonText}>🎰 Oyna</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0c0f", alignItems: "center", justifyContent: "center", padding: 20 },
  title: { fontSize: 48, fontWeight: "700", color: "#d4a843", textAlign: "center", marginBottom: 10 },
  subtitle: { fontSize: 18, color: "#6b7585", marginBottom: 40 },
  button: { backgroundColor: "#d4a843", paddingVertical: 16, paddingHorizontal: 40, borderRadius: 32 },
  buttonText: { color: "#000", fontSize: 20, fontWeight: "700" },
});

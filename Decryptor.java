
import android.content.Context;
import android.os.Looper;
import java.lang.reflect.Method;
import java.lang.reflect.Field;

public class Decryptor {
    public static void main(String[] args) {
        try {
            System.out.println("Preparing Looper...");
            try {
                Looper.prepareMainLooper();
            } catch (Exception le) {
                // Already prepared or failed, continue
            }
            
            System.out.println("Loading native-lib...");
            String libPath = args[0];
            System.load(libPath);
            System.out.println("Native-lib loaded successfully!");
            
            System.out.println("Obtaining System Context...");
            Class<?> activityThreadClass = Class.forName("android.app.ActivityThread");
            Object activityThread = activityThreadClass.getMethod("systemMain").invoke(null);
            Context systemContext = (Context) activityThreadClass.getMethod("getSystemContext").invoke(activityThread);
            System.out.println("System context: " + systemContext);
            
            System.out.println("Creating Package Context for com.sportzx.live...");
            Context context = systemContext.createPackageContext("com.sportzx.live", 
                Context.CONTEXT_INCLUDE_CODE | Context.CONTEXT_IGNORE_SECURITY);
            System.out.println("Package Context package name: " + context.getPackageName());
            
            String encryptedData = args[1];
            if (encryptedData.startsWith("@")) {
                String filePath = encryptedData.substring(1);
                System.out.println("Reading encrypted payload from file: " + filePath);
                java.io.File file = new java.io.File(filePath);
                java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.FileReader(file));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();
                encryptedData = sb.toString();
            }
            System.out.println("Data length to decrypt: " + encryptedData.length());
            
            Class<?> dataHelperClass = Class.forName("com.sportzx.live.helpers.DataHelper");
            Object instance = dataHelperClass.getField("INSTANCE").get(null);
            Method helpMethod = dataHelperClass.getMethod("help", Context.class, String.class);
            
            System.out.println("Invoking DataHelper.help...");
            String decrypted = (String) helpMethod.invoke(instance, context, encryptedData);
            System.out.println("DECRYPTION RESULT START");
            System.out.println(decrypted);
            System.out.println("DECRYPTION RESULT END");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}

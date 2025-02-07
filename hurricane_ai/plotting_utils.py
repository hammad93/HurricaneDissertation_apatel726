import matplotlib.pyplot as plt
import simplekml
from sklearn.preprocessing import RobustScaler
from hurricane_ai.container.hurricane_data_container import HurricaneDataContainer
import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

def plot_error_loss(predictions: list, observations: list, history: dict, is_scaled: bool, scaler: RobustScaler = None,
                    var_index: int = None) -> plt:
    """
    Generates two-figure plot including model error histogram and loss curve.

    :param predictions: The vector of model predictions.
    :param observations: The vector of ground-truth observations.
    :param history: Model training history (from which to generate loss curve).
    :param is_scaled: Indicates whether predicted/observed values have been scaled back to their original values.
    :param scaler: Fitted scaler used for inverting scaled values back to their original range.
    :param var_index: Index of the variable (that the model was trained to predict) within the feature vector.
    """
    if not is_scaled:
        # Ensure that scaler has also been passed in
        assert scaler is not None and var_index is not None, \
            'Fitted scaler and variable index must be provided if data are not pre-scaled for plotting.'

        feature_length = len(scaler.center_)

        # Scale predictions
        predictions = [scaler.inverse_transform(
            [_generate_sparse_feature_vector(feature_length, var_index, wind[0]) for wind in prediction]) for prediction
            in predictions]

        # Scale ground-truth observations
        observations = [scaler.inverse_transform(
            [_generate_sparse_feature_vector(feature_length, var_index, wind[0]) for wind in observation]) for
            observation in observations]

    # Compute errors between predicted and actual
    errors = []
    for i in range(len(predictions)):
        for j in range(len(predictions[i])):
            # Calculate errors
            error = predictions[i][j] - observations[i][j]
            errors.append(error)

    # Generate error histogram
    plt.figure(1)
    plt.hist(errors, bins=50)
    plt.title('Error Distribution')
    plt.xlabel('Error')
    plt.ylabel('Frequency')
    plt.grid(True)

    # Generate loss curve
    plt.figure(2)
    plt.plot(history['loss'])
    plt.plot(history['val_loss'])
    plt.title('Model Loss')
    plt.ylabel('Loss')
    plt.xlabel('Epoch')
    plt.legend(['train', 'test'], loc='upper left')

    return plt


def _generate_sparse_feature_vector(vector_length: int, feature_index: int, feature_value: float):
    """
    Creates sparse (0-vector) with feature value inserted (used for inputting to scaler).

    :param vector_length: Length of the feature vector.
    :param feature_index: Index of the inserted feature in the sparse feature vector.
    :param feature_value: Feature value to insert into the sparse feature vector.
    """
    features = [0] * vector_length
    features[feature_index] = feature_value

    return features

def process_results(results, postfix = '') :   
    for storm in results['inference'].values() :
        plt.figure(f"{storm['name']}{postfix}")
        ax = plt.axes(projection=cartopy.crs.PlateCarree())

        ax.add_feature(cartopy.feature.LAND)
        ax.add_feature(cartopy.feature.OCEAN)
        ax.add_feature(cartopy.feature.COASTLINE)
        #ax.add_feature(cartopy.feature.BORDERS, linestyle=':')
        #ax.add_feature(cartopy.feature.LAKES, alpha=0.5)
        #ax.add_feature(cartopy.feature.RIVERS)

        ax.set_global()
        # open kml object for writing files
        kml = simplekml.Kml()
        for index in range(len(storm['lat'])) :
            # process PNG
            ax.plot([storm['lon'][index - 1], storm['lon'][index]], [storm['lat'][index - 1], storm['lat'][index]],
                     color='gray', linestyle='--',
                     transform=ccrs.PlateCarree())
            
            # process KML
            pnt = kml.newpoint(name = f'{storm["name"]} + delta {index}',
                               description = f'{storm["wind"][index]:.2f} knots\n' +
                               f'{storm["times"][index]}\n' +
                               f'({storm["lon"][index]}, {storm["lat"][index]}) (Lon, Lat)',
                               coords = [(storm['lon'][index], storm['lat'][index])])
            pnt.timestamp.when = str(storm['times'][index])
            pnt.extendeddata.newdata(name = 'wind', value = storm["wind"][index], displayname = 'Wind Intensity (knots)')
        
        # add track
        data_container = HurricaneDataContainer()
        data = data_container._parse(results['track'])
        print(data.head())
        
        for index, row in data[['entry_time', 'lat', 'long', 'max_wind', 'min_pressure']].iterrows() :
            pnt = kml.newpoint(name = f'{storm["name"]} history - delta {index}',
                               description = f'{row["max_wind"]} knots\n' +
                               f'{row["entry_time"]}\n' +
                               f'({row["long"]}, {row["lat"]}) (Lon, Lat)',
                               coords = [(float(row['long'][:-1]) * -1, float(row['lat'][:-1]))]
                              )
            pnt.style.iconstyle.color = simplekml.Color.red
            
        # save results
        kml.save(f'results/{postfix}.kml')
        plt.savefig(f'results/{postfix}.png', dpi=300)
        plt.close('all')